# Local Laya service

This service runs [`convaiinnovations/laya`](https://huggingface.co/convaiinnovations/laya),
a small model that answers specific decision questions. It provides `GET /health`
to check whether it is running and `POST /decide` to ask it a question.
The Service Desk API uses it to check requests and suggest case labels
(see `../api/app/services/laya_decisions.py`).

Two ways to run it: in Docker (default) or natively on a Mac (faster, recommended
for local development on Apple Silicon).

## Option A — Docker (default stack)

```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8010/health
```

Notes:

- First start downloads ~1.5 GB of weights into the `service_desk_hf` volume and
  pip-installs torch + CUDA wheels, so the `laya` image build takes a long time.
- `.env` uses `LAYA_BASE_URL=http://laya:8010` for container-to-container traffic.

## Option B — native Mac service (Apple Silicon, torch + MPS)

Why: Laya is a 421M-param BERT encoder with a custom decision head — MLX-LM and
Ollama/GGUF only serve decoder LLMs, so there is no conversion path. Native
torch with MPS is the optimized Mac path, and you reuse this exact `app.py`
unchanged. The API container reaches it via `host.docker.internal`.

### 1. One-time setup

```bash
uv venv .venv-laya --python 3.12
uv pip install --python .venv-laya/bin/python \
  "torch" "laya==0.3.4" "fastapi==0.141.1" "uvicorn[standard]"

# verify MPS acceleration is available
.venv-laya/bin/python -c \
  "import torch; print(torch.__version__, torch.backends.mps.is_available())"
```

Downloads: ~2 GB pip packages, plus ~808 MB (english) + ~647 MB (multilingual)
model weights into the Hugging Face cache on first inference.

### 2. Start

```bash
USE_TF=0 LAYA_ROUTE_MODE=router LAYA_PRELOAD=true LAYA_MAX_LOADED=2 \
  LAYA_DEVICE=mps LAYA_MODEL=convaiinnovations/laya \
  nohup .venv-laya/bin/python -m uvicorn app:app \
  --host 0.0.0.0 --port 8010 --app-dir apps/laya \
  > /tmp/laya-mac.log 2>&1 & echo "laya pid $!"
```

`USE_TF=0` avoids a known transformers/TensorFlow import deadlock.
`LAYA_DEVICE=mps` uses the Apple GPU; use `cpu` (or empty) if you hit MPS issues.

### 3. Point the API at it and recreate (not just restart)

```bash
# .env
LAYA_BASE_URL=http://host.docker.internal:8010
```

```bash
docker compose up -d api   # recreate picks up .env; `restart` does NOT
```

### 4. Verify end to end

```bash
curl http://localhost:8010/health          # native service
docker compose exec api sh -c \
  "python -c \"import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:8010/health', timeout=10).read().decode())\""
python3 scripts/evaluate.py                # expect 13/14+ incl. all security checks
```

## Status checks

```bash
curl -s http://localhost:8010/health
# {"status":"ok","strategy":"router","model":"convaiinnovations/laya",
#  "preload":"true","loaded":true}
```

- `loaded: false` means no checkpoint is warm yet — the first `/decide` call
  downloads weights and takes minutes; subsequent calls are sub-second.
- `strategy` mirrors `LAYA_ROUTE_MODE` (`router` or `single`).
- Live log: `tail -f /tmp/laya-mac.log` (native) or `docker compose logs laya` (Docker).
- Confirm the API actually reaches it: a run artifact's `security_signals`
  should show `"provider": "laya"`, not `"unavailable"`.

## Stop

```bash
kill <pid>              # native service started with nohup above
docker compose stop laya  # Docker variant (only if it was started)
```

The service does not auto-start on reboot. For persistence, wrap the start
command in a `launchd` plist (`~/Library/LaunchAgents/ai.service-desk.laya.plist`)
with `RunAtLoad` set.

## Troubleshooting

| Symptom | Fix |
|---|---|
| API `security_signals.provider` is `"unavailable"` | Service down or wrong URL; check health from inside the container (step 4) |
| Changed `.env` but behavior is stale | `docker compose up -d api` — `restart` keeps old env |
| Port 8010 already in use | Native + Docker services collide; run only one |
| MPS errors on old macOS/torch | `LAYA_DEVICE=cpu` (model card: 193–464 ms/call on CPU — fine for a guard) |
| `/decide` intermittently returns 503 with `index … out of bounds` | torch 2.14 + MPS uninitialized-memory bug (observed 2026-10). Restart with CPU: `LAYA_DEVICE_OVERRIDE=cpu scripts/native_services.sh down && LAYA_DEVICE_OVERRIDE=cpu scripts/native_services.sh up` |
| `laya.load()` hangs at startup | Ensure `USE_TF=0` is set |
| English-only demo, low RAM | `LAYA_ROUTE_MODE=single` loads just the english checkpoint |
