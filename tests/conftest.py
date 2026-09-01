import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import os
import shutil

TEST_ROOT = Path(__file__).parent / ".runtime"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("THISTINTI_DATABASE_URL", f"sqlite:///{TEST_ROOT / 'test.db'}")
os.environ["THISTINTI_STORAGE_DIR"] = str(TEST_ROOT / "uploads")
os.environ["THISTINTI_QUARANTINE_DIR"] = str(TEST_ROOT / "quarantine")
os.environ["THISTINTI_REJECTED_DIR"] = str(TEST_ROOT / "rejected")
os.environ["THISTINTI_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["THISTINTI_ALLOW_REGISTRATION"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import Base, engine
from app.main import app, _rate_buckets
from app.models import Document


_SYNTHETIC_PROVENANCE_PREFIXES = ("property-", "currency-", "delivered-")


def _materialize_synthetic_provenance_bytes(mapper, connection, target: Document) -> None:
    """Give property/stateful Document fixtures real stored bytes.

    The provenance property suites construct Documents directly instead of using the
    upload endpoint. Stored-byte qualification now requires those fixtures to model
    the same invariant as production: ``file_hash`` must match bytes at
    ``storage_path``. Restrict this hook to the known synthetic fixture filenames so
    tests for missing/substituted storage remain meaningful.
    """
    source_filename = target.source_filename or ""
    if not source_filename.startswith(_SYNTHETIC_PROVENANCE_PREFIXES):
        return
    path = Path(target.storage_path)
    payload = f"synthetic-provenance:{target.id}:{source_filename}".encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    target.file_hash = hashlib.sha256(payload).hexdigest()


event.listen(Document, "before_insert", _materialize_synthetic_provenance_bytes)


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
