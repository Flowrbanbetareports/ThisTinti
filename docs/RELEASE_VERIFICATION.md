# Verifica release 3.0.0

## Comandi principali

```bash
python -m pytest -q
python -m coverage run -m pytest
python -m coverage report -m --fail-under=90
python -m ruff check app tests scripts migrations
python -m ruff format --check app tests scripts migrations
python -m bandit -q -r app scripts -x tests
node --check app/static/app.js
python -m alembic upgrade head
python -m alembic check
python -m alembic downgrade base
python -m alembic upgrade head
python scripts/run_validation_gate.py
python scripts/http_smoke.py
python scripts/generate_sbom.py
python scripts/generate_openapi.py
```

## Risultato osservato

- 61 test passati.
- 92% di copertura.
- Nessun problema Ruff o Bandit.
- Migrazione adattiva `9b3f17a42d91` reversibile.
- Gate di validazione superato.
- Smoke HTTP superato con 4 documenti, 1 catena, 5 casi, readiness positiva e audit valido.
