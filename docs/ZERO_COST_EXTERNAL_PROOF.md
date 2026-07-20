# Prova esterna a costo zero

Questa procedura dimostra il comportamento di ThisTinti su infrastruttura diversa dal computer di sviluppo senza acquistare hosting.

## Cosa è già verificato

- suite locale: 121 test superati e copertura applicativa del 91%;
- migrazioni SQLite reversibili e allineate;
- Validation Gate sintetico, smoke HTTP, backup, verifica e restore;
- prova app/worker locale con proposta, fattura e pagamento, Proof Graph, rischio preventivo, self-red-team, job persistenti, riavvio e file invariati;
- PostgreSQL cloud Supabase: ruolo runtime senza `SUPERUSER`/`BYPASSRLS`, un solo tenant visibile per contesto e rifiuto cross-tenant `42501`;
- advisor di sicurezza Supabase senza segnalazioni.

## Cosa esegue GitHub Actions

Il job `postgres-external-proof`:

1. crea PostgreSQL 16 in una macchina GitHub effimera;
2. crea ruoli distinti per migrazioni e runtime;
3. applica Alembic come owner;
4. prova RLS e trigger cross-tenant come runtime;
5. avvia FastAPI e il worker in processi separati;
6. accoda ed elabora proposta, fattura e pagamento JSON non sensibili;
7. controlla Proof Graph, simulazione preventiva, self-red-team, file, job, readiness e audit;
8. riavvia app e worker;
9. ricontrolla persistenza e integrità;
10. conserva report e log per 14 giorni.

Non vengono usati segreti di produzione, documenti aziendali o API a pagamento.

## Pubblicazione del repository

Dal checkout pulito:

```bash
gh auth login
bash scripts/publish_github.sh thistinti-staging
```

Lo script crea un repository privato nell'account autenticato quando non esiste, configura `origin` e pubblica il ramo corrente. GitHub Actions parte al primo push.

In alternativa, clonare il bundle Git consegnato con la release:

```bash
git clone ThisTinti-3.2.0-alpha.1.gitbundle thistinti-staging
cd thistinti-staging
gh auth login
gh repo create thistinti-staging --private --source=. --remote=origin --push
```

## Evidenza minima per dichiarare la prova riuscita

- job GitHub verde;
- artifact `thistinti-external-proof-*` scaricato;
- `report.json` con `passed: true` e due fasi;
- `postgres-roles.txt` con `super=false` e `bypassrls=false`;
- `alembic-version.txt` con `d42a0f61be90`;
- nessun dato reale nei log o negli artifact.

Questa prova dimostra portabilità e comportamento tecnico. Non sostituisce pilot documentale reale, load test, scanner malware operativo, penetration test o revisione privacy.
