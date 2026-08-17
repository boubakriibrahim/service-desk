import os
import shutil
import tempfile
from pathlib import Path
import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
API_ROOT = Path(__file__).resolve().parents[2]
# apps/api -> repo root locally; /app -> / inside the API image, where demo/ is mounted at /demo.
DEMO_DOCUMENTS = os.environ.get("DEMO_DOCUMENTS_PATH") or str(API_ROOT.parent.parent / "demo" / "documents")

if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL is not set; integration tests need a PostgreSQL with pgvector", allow_module_level=True)
# The session fixture drops the public schema, so only ever run against a dedicated test database.
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0].endswith("_test"):
    raise pytest.UsageError("TEST_DATABASE_URL must point at a database whose name ends with _test")

STORAGE = tempfile.mkdtemp(prefix="service-desk-uploads-")
os.environ.update({
    "DATABASE_URL": TEST_DATABASE_URL,
    "AI_MODE": "demo",
    "LAYA_MODE": "demo",
    "EMBEDDING_MODE": "demo",
    "APP_ENV": "test",
    "SECRET_KEY": "integration-test-secret-key-0123456789abcdef",
    "DEMO_DOCUMENTS_PATH": DEMO_DOCUMENTS,
    "FILE_STORAGE_PATH": STORAGE,
})

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
from .helpers import login  # noqa: E402

# The engine is built when app.db is first imported. If anything imported it before the
# environment above was set, it would point at the real database, so check it directly.
if not (engine.url.database or "").endswith("_test"):
    raise pytest.UsageError(f"Refusing to reset {engine.url.database!r}: the API engine must use a database ending with _test")


@pytest.fixture(scope="session", autouse=True)
def database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
    seed()
    yield
    engine.dispose()
    shutil.rmtree(STORAGE, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state(database):
    with TestClient(app) as client:
        login(client, "manager@demo.local")
        assert client.post("/api/admin/reset-demo").status_code == 200
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def as_user():
    def make(email: str) -> TestClient:
        c = TestClient(app)
        assert login(c, email).status_code == 200
        return c
    return make
