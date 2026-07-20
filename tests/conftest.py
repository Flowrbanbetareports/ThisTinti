import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import os
import shutil

TEST_ROOT = Path(__file__).parent / ".runtime"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["THISTINTI_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["THISTINTI_STORAGE_DIR"] = str(TEST_ROOT / "uploads")
os.environ["THISTINTI_QUARANTINE_DIR"] = str(TEST_ROOT / "quarantine")
os.environ["THISTINTI_REJECTED_DIR"] = str(TEST_ROOT / "rejected")
os.environ["THISTINTI_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["THISTINTI_ALLOW_REGISTRATION"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app, _rate_buckets


@pytest.fixture(autouse=True)
def reset_db():
    _rate_buckets.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    for directory in (TEST_ROOT / "uploads", TEST_ROOT / "quarantine", TEST_ROOT / "rejected"):
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth(client):
    response = client.post(
        "/api/auth/register",
        headers={"X-Session-Mode": "token"},
        json={
            "organization_name": "Test Company",
            "email": "admin@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}
