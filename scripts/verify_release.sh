#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TMP="$(mktemp -d -t thistinti-verify-XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

export THISTINTI_ENV=test
export THISTINTI_DATABASE_URL="sqlite:///$TMP/verify.db"
export THISTINTI_STORAGE_DIR="$TMP/uploads"
export THISTINTI_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export THISTINTI_AUTO_CREATE_SCHEMA=false
export THISTINTI_ALLOW_REGISTRATION=true
export THISTINTI_SECURE_COOKIES=false
export COVERAGE_FILE="$TMP/.coverage"

python -m ruff check app tests scripts migrations
python -m ruff format --check app tests scripts migrations
python -m bandit -q -r app scripts -x tests
python -m compileall -q app scripts
if command -v node >/dev/null 2>&1; then
  node --check app/static/app.js
  node --check site/site.js
fi
bash scripts/run_test_coverage.sh
python scripts/run_python_gate.py path scripts/check_dependencies.py
python scripts/run_python_gate.py path scripts/check_legal_distribution.py
python scripts/run_python_gate.py module alembic.__main__ upgrade head
python scripts/run_python_gate.py module alembic.__main__ check
python scripts/run_python_gate.py module alembic.__main__ downgrade base
python scripts/run_python_gate.py module alembic.__main__ upgrade head
python scripts/run_python_gate.py path scripts/run_validation_gate.py
python scripts/run_python_gate.py path scripts/http_smoke.py

BACKUP="$TMP/verification-backup.zip"
python scripts/run_python_gate.py path scripts/backup_system.py "$BACKUP" --database-only
python scripts/run_python_gate.py path scripts/verify_backup.py "$BACKUP"
python scripts/run_python_gate.py path scripts/restore_backup.py "$BACKUP" \
  --sqlite-database "$TMP/restored.db" --storage-dir "$TMP/restored-storage"
python scripts/run_python_gate.py path scripts/generate_sbom.py
python scripts/run_python_gate.py path scripts/generate_openapi.py
python scripts/verify_release.py --internal-checks

echo "Release verification passed"
