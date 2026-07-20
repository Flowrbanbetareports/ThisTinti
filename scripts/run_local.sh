#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p data/uploads
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
