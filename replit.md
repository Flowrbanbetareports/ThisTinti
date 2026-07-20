# Deploy su Replit

ThisTinti può essere eseguito su Replit, ma un deployment persistente richiede PostgreSQL e storage persistente/esterno.

## Secrets

- `THISTINTI_ENV=production`
- `THISTINTI_SECRET_KEY`: almeno 48 caratteri casuali;
- `THISTINTI_DATABASE_URL`: PostgreSQL persistente;
- `THISTINTI_STORAGE_DIR`: directory persistente o adapter object storage;
- `THISTINTI_ALLOW_REGISTRATION=false` dopo il primo amministratore;
- `THISTINTI_AUTO_CREATE_SCHEMA=false`;
- `THISTINTI_SECURE_COOKIES=true`;
- `THISTINTI_CORS_ORIGINS`: URL pubblico esatto del deployment.

## Comando

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Limiti

- non usare SQLite con più istanze;
- verificare persistenza dei file dopo riavvio;
- applicare HTTPS e cookie Secure;
- aggiungere monitoraggio esterno;
- non inserire segreti nel repository o nei file pubblici.

Nessun deployment è stato eseguito automaticamente dal pacchetto.
