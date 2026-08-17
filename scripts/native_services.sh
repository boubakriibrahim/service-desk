#!/usr/bin/env bash
# Start/stop the native (non-container) model services: Laya (8010) + embeddings (8090).
# Auto-detects the best device: Apple Silicon -> mps, NVIDIA -> cuda, else cpu.
# Usage: scripts/native_services.sh up|down|status
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=".venv-laya"
LAYA_PORT="${LAYA_NATIVE_PORT:-8010}"
EMB_PORT="${EMB_NATIVE_PORT:-8090}"
LAYA_LOG="/tmp/laya-native.log"
EMB_LOG="/tmp/embeddings-native.log"
PIDFILE_LAYA="/tmp/service-desk-laya.pid"
PIDFILE_EMB="/tmp/service-desk-embeddings.pid"

command -v uv >/dev/null 2>&1 || { echo "uv is required — install it: https://docs.astral.sh/uv/" >&2; exit 1; }
[ -x "$VENV/bin/python" ] || { echo "venv missing; run: make native-prepare" >&2; exit 1; }

detect_device() {
  "$VENV/bin/python" - <<'EOF'
import torch, platform
if torch.backends.mps.is_available() and torch.backends.mps.is_built():
    print("mps")
elif torch.cuda.is_available():
    print("cuda")
elif platform.system() == "Darwin" and platform.machine() == "arm64":
    print("cpu")
else:
    print("cpu")
EOF
}

is_up() { # $1=pidfile
  [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

start_service() { # $1=name $2=app-dir $3=port $4=log $5=pidfile $6=device
  local name="$1" app_dir="$2" port="$3" log="$4" pidfile="$5" device="$6"
  if is_up "$pidfile"; then
    echo "$name already running (pid $(cat "$pidfile"), device $(cat "${pidfile%.pid}.device" 2>/dev/null || echo "?"))"
    return 0
  fi
  USE_TF=0 LAYA_DEVICE="$device" EMB_DEVICE="$device" \
    nohup "$VENV/bin/python" -m uvicorn app:app --host 0.0.0.0 --port "$port" \
    --app-dir "$app_dir" > "$log" 2>&1 &
  local pid=$!
  echo "$pid" > "$pidfile"
  echo "$device" > "${pidfile%.pid}.device"
  echo "$name starting on $device (port $port, pid $pid) — log: $log"
}

stop_service() { # $1=name $2=pidfile
  local name="$1" pidfile="$2"
  if is_up "$pidfile"; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile" "${pidfile%.pid}.device"
    echo "$name stopped"
  else
    echo "$name not running"
    rm -f "$pidfile" "${pidfile%.pid}.device"
  fi
}

case "${1:-up}" in
  up)
    DEVICE="${LAYA_DEVICE_OVERRIDE:-$(detect_device)}"
    start_service "laya"      "apps/laya"      "$LAYA_PORT" "$LAYA_LOG" "$PIDFILE_LAYA" "$DEVICE"
    start_service "embeddings" "apps/embeddings" "$EMB_PORT" "$EMB_LOG" "$PIDFILE_EMB"  "$DEVICE"
    echo "Waiting for health..."
    for i in $(seq 1 30); do
      L=$(curl -sf "http://localhost:$LAYA_PORT/health" 2>/dev/null && echo OK || echo waiting)
      E=$(curl -sf "http://localhost:$EMB_PORT/health" 2>/dev/null && echo OK || echo waiting)
      [ "$L" = "OK" ] && [ "$E" = "OK" ] && break
      sleep 2
    done
    echo "laya:      $(curl -sf "http://localhost:$LAYA_PORT/health" 2>/dev/null || echo 'not ready yet (first call downloads weights)')"
    echo "embeddings:$(curl -sf "http://localhost:$EMB_PORT/health" 2>/dev/null || echo 'not ready yet (first call downloads model)')"
    ;;
  down)
    stop_service "laya" "$PIDFILE_LAYA"
    stop_service "embeddings" "$PIDFILE_EMB"
    ;;
  status)
    for s in laya:$PIDFILE_LAYA embeddings:$PIDFILE_EMB; do
      name="${s%%:*}"; pf="${s#*:}"
      if is_up "$pf"; then
        echo "$name: up (pid $(cat "$pf"), device $(cat "${pf%.pid}.device" 2>/dev/null || echo "?"))"
      else
        echo "$name: down"
      fi
    done
    ;;
  *)
    echo "Usage: $0 up|down|status" >&2; exit 1
    ;;
esac
