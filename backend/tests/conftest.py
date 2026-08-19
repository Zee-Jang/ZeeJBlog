from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


_temp_dir = tempfile.TemporaryDirectory(prefix="zeej-blog-tests-")
_db_path = Path(_temp_dir.name) / "test.db"

# Settings and the SQLAlchemy engine are created during module import, so the
# isolated test configuration must be installed before importing app.main.
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_db_path.as_posix()}",
        "SECRET_KEY": "test-only-secret-key-32-characters",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_PASSWORD": "TestAdmin123",
        "ADMIN_NAME": "Test Admin",
        "MAIL_DEV_MODE": "false",
        "SEED_DEFAULT_INVITE": "false",
        "DEEPSEEK_API_KEY": "",
    }
)

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def cleanup_database() -> Generator[None, None, None]:
    yield
    engine.dispose()
    _temp_dir.cleanup()
