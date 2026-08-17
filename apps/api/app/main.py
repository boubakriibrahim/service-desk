import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import admin, approvals, auth, runs, settings, sources, work
from sqlalchemy import text
from app.config import get_settings, validate_runtime_settings
from app.db import engine

app_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_settings(app_settings)
    storage = Path(app_settings.file_storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    # Fail at startup rather than on the first upload, e.g. for a volume created by a root container.
    if not os.access(storage, os.W_OK):
        raise RuntimeError(
            f"FILE_STORAGE_PATH {storage} is not writable by the API user (uid {os.getuid()}). "
            f"Fix it with: docker compose run --rm --user root api chown -R 10001:10001 {storage}"
        )
    yield


docs_off = {"docs_url": None, "redoc_url": None, "openapi_url": None} if app_settings.is_production else {}
app = FastAPI(title="Service Desk API", version="0.1.0", lifespan=lifespan, **docs_off)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(work.router)
app.include_router(sources.router)
app.include_router(approvals.router)
app.include_router(runs.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "service-desk-api"}


@app.get("/health/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "database unreachable"})
    return {"status": "ready", "service": "service-desk-api"}
