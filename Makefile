# LOCAL_RUNN (in .env) selects how GPU-bound model services (Laya, embeddings) run:
#   native = uv-managed venvs with auto device detection (Apple Silicon -> MPS,
#            NVIDIA -> CUDA, else CPU); the laya container is skipped.
#   docker = Docker Compose (laya container on CPU; heavier image build).
#   off    = start no local model services (use demo modes or external endpoints).
LOCAL_RUNN := $(shell sed -n 's/^LOCAL_RUNN=//p' .env 2>/dev/null | head -n1)

LOCAL := $(filter native,$(LOCAL_RUNN))
DOCKER_MODELS := $(filter docker,$(LOCAL_RUNN))
TEST_DB := service_desk_test

.PHONY: init up up-laya down logs ps reset test test-integration smoke eval native-prepare native-up native-down

init:
	@test -f .env || cp .env.example .env

up: init
	@if [ "$(LOCAL)" = "native" ]; then make native-prepare && ./scripts/native_services.sh up; fi
	@if [ "$(LOCAL)" = "native" ]; then docker compose up -d --build db api web; \
	elif [ -n "$(DOCKER_MODELS)" ]; then COMPOSE_PROFILES=models docker compose up -d --build; \
	else docker compose up -d --build; fi

up-laya: init
	@if [ "$(LOCAL)" = "native" ]; then make native-prepare && ./scripts/native_services.sh up; \
	else COMPOSE_PROFILES=models docker compose up -d --build db api web laya; fi

native-prepare:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required for LOCAL_RUNN=native — install it: https://docs.astral.sh/uv/"; exit 1; }
	@[ -x .venv-laya/bin/python ] || uv venv --quiet .venv-laya --python 3.12
	@uv pip install --python .venv-laya/bin/python --quiet \
		"torch" "laya==0.3.4" "sentence-transformers" "fastapi==0.141.1" "uvicorn[standard]"

# Start/stop the native Laya + embedding services (auto device detection).
native-up: native-prepare
	@./scripts/native_services.sh up

native-down:
	@./scripts/native_services.sh down

down:
	@if [ "$(LOCAL)" = "native" ]; then ./scripts/native_services.sh down; fi
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# Removes the database and upload volumes. The next `make up` re-seeds the demo.
reset:
	docker compose down -v

test:
	docker compose run --rm api pytest -q

# Runs the API integration tests against a throwaway database in the running db container.
# The test URL reuses DATABASE_URL from .env with the database name swapped, so a custom
# password carries over. The test database is dropped even when a test fails.
test-integration:
	docker compose exec -T db psql -U service_desk -d service_desk -qc "DROP DATABASE IF EXISTS $(TEST_DB)" -c "CREATE DATABASE $(TEST_DB)"
	docker compose run --rm api sh -c 'TEST_DATABASE_URL="$${DATABASE_URL%/*}/$(TEST_DB)" pytest -q'; \
	status=$$?; \
	docker compose exec -T db psql -U service_desk -d service_desk -qc "DROP DATABASE IF EXISTS $(TEST_DB)"; \
	exit $$status

smoke:
	python3 scripts/smoke.py

eval:
	python3 scripts/evaluate.py
