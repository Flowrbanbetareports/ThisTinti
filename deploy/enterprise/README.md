# Deploy self-hosted

Questa cartella è una configurazione di riferimento gratuita e non un servizio gestito.

1. Leggere `../../TERMS_OF_USE.md`, `../../DISCLAIMER.md`, `../../SUPPORT.md` e `../../docs/RESPONSIBILITY_MATRIX.md`.
2. Eseguire `python ../../scripts/enterprise_init.py --host ... --accept-operator-responsibility --accept-no-support` dalla radice del repository.
3. Eseguire il preflight.
4. Avviare Docker Compose.
5. Creare il primo amministratore tramite il servizio `admin-bootstrap`.
6. Completare `../../docs/ENTERPRISE_ACCEPTANCE_CHECKLIST.md` prima dell’uso reale.

I file `.env`, `operator-acceptance.json`, `secrets/`, `backups/` e `logs/` non devono essere pubblicati.
