.PHONY: install migrate run test coverage lint security validation check verify package

install:
	python -m pip install -r requirements-dev.txt

migrate:
	alembic upgrade head

run:
	python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

test:
	pytest

coverage:
	coverage run --source=app -m pytest && coverage report --skip-covered --fail-under=90

lint:
	ruff check app tests scripts migrations
	ruff format --check app tests scripts migrations

security:
	bandit -q -r app scripts -x tests

validation:
	python scripts/run_validation_gate.py
	python scripts/http_smoke.py

check: lint security
	python -m compileall -q app scripts
	node --check app/static/app.js
	python scripts/check_dependencies.py
	python scripts/check_legal_distribution.py
	python scripts/check_publication_readiness.py

verify:
	python scripts/verify_release.py

package: verify
	python scripts/package_release.py
