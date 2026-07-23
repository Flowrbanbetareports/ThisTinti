# Manuale operativo — ThisTinti 3.4.0-alpha.5

## Profili di ambiente

### Sviluppo

- SQLite consentito;
- registrazione pubblica abilitabile;
- cookie non `Secure` su HTTP locale;
- rate limiting in memoria consentito;
- scanner esterno facoltativo;
- ingestion sincrona consentita.

### Produzione

L'avvio viene rifiutato se non sono rispettati almeno questi requisiti:

```env
THISTINTI_ENV=production
THISTINTI_PROCESS_ROLE=app              # worker nel processo worker
THISTINTI_DATABASE_URL=postgresql+psycopg://...
THISTINTI_SECRET_KEY=<segreto casuale forte>
THISTINTI_AUTO_CREATE_SCHEMA=false
THISTINTI_SECURE_COOKIES=true
THISTINTI_ALLOW_REGISTRATION=false
THISTINTI_DATABASE_RATE_LIMITING=true
THISTINTI_ASYNC_INGESTION_ENABLED=true
THISTINTI_ALLOW_SYNCHRONOUS_INGESTION=false
THISTINTI_REQUIRE_MALWARE_SCANNER=true
THISTINTI_MALWARE_SCANNER_COMMAND=clamdscan
```

Il solo fatto che il comando dello scanner esista non rende il servizio pronto: `/api/readiness` crea un file pulito temporaneo ed esegue una scansione reale. Un daemon irraggiungibile produce HTTP 503.

## Processi

Tre ruoli devono essere separati:

1. **migrate** — esegue `alembic upgrade head` e termina;
2. **app** — serve API e interfaccia;
3. **worker** — reclama ed esegue job persistenti.

```bash
THISTINTI_PROCESS_ROLE=migrate alembic upgrade head
THISTINTI_PROCESS_ROLE=app uvicorn app.main:app --host 0.0.0.0 --port 8000
THISTINTI_PROCESS_ROLE=worker python scripts/run_worker.py --poll-seconds 1
```

Il worker usa lease e heartbeat. Un processo subentrante recupera i job il cui lease è scaduto. I retry sono limitati e applicano backoff; gli errori definitivi restano consultabili.

## Endpoint di servizio

- `/api/health`: il processo HTTP risponde;
- `/api/readiness`: verifica database, storage, quarantena, rifiutati, configurazione, OCR, scanner e heartbeat worker;
- `/api/system/workers`: worker osservati, stato e indicazione `stale`;
- `/api/audit/verify`: verifica della catena audit per il tenant.

L'orchestratore deve usare esclusivamente `/api/readiness` per il traffico produttivo.

## Migrazioni

```bash
alembic current
alembic upgrade head
alembic check
```

Prima di applicare una migrazione:

1. creare e verificare un backup;
2. provare upgrade e restore su staging;
3. verificare lo spazio libero;
4. impedire l'avvio simultaneo di più processi migrate;
5. conservare log e versione dell'artefatto.

La migrazione 3.1 introduce sessioni, sequenza audit, job, heartbeat, chiavi API, contatori rate limit e protezioni PostgreSQL RLS/trigger.

## Quarantena e scanner malware

Ogni file asincrono entra in `THISTINTI_QUARANTINE_DIR`. Prima del parsing vengono eseguiti:

- blocco di intestazioni eseguibili;
- rilevazione del marker EICAR;
- scanner esterno, se configurato;
- controlli specifici per XML, P7M, ZIP, XLSX e PDF.

In produzione lo scanner deve fallire in modo chiuso. Aggiornare le firme fuori dal processo applicativo e monitorarne età, daemon, errori e latenza. Non montare la quarantena come volume pubblico.

## Chiavi API

Le chiavi hanno formato `ttk_<id>.<segreto>` e il segreto viene mostrato una sola volta. Conservare la chiave in un secret manager, non in file di progetto o log.

Scope disponibili:

- `read`: consultazione;
- `ingest`: creazione di job di ingestione;
- `review`: decisioni e operazioni da revisore.

Revocare una chiave non più necessaria e preferire chiavi separate per integrazione, ambiente e finalità. Le chiavi non possono usare il logout delle sessioni utente.

## Backup

### Creazione

```bash
python scripts/backup_system.py /secure-backups/thistinti-2026-07-19.zip
```

Per SQLite viene usata l'API backup coerente. Per PostgreSQL viene creato un dump custom tramite `pg_dump`. Lo storage viene incluso salvo `--database-only`.

### Verifica

```bash
python scripts/verify_backup.py /secure-backups/thistinti-2026-07-19.zip
```

La verifica controlla percorsi, duplicati, manifest, hash, integrità SQLite o leggibilità del dump PostgreSQL.

### Ripristino

```bash
python scripts/restore_backup.py /secure-backups/thistinti-2026-07-19.zip \
  --sqlite-database /restore/thistinti.db \
  --storage-dir /restore/data
```

Il restore non sovrascrive destinazioni esistenti senza opzione esplicita. Per PostgreSQL usare un database vuoto e la conferma richiesta dallo script.

Un backup è valido soltanto dopo una prova periodica di restore con: readiness verde, download di un campione, audit valido e conteggi confrontati.

## Monitoraggio minimo

Raccogliere e allertare su:

- HTTP 5xx e readiness 503;
- job in coda, età del job più vecchio, retry e fallimenti definitivi;
- heartbeat worker stale;
- latenza OCR, parsing, scanner e analisi;
- upload e batch rifiutati;
- spazio di storage/quarantena/database;
- pool e lock PostgreSQL;
- login falliti, revoche e rate limit;
- esito della verifica audit;
- successo, età e restore dei backup;
- età firme malware e certificati HTTPS.

## Incident response

1. rimuovere il servizio dal traffico senza cancellare volumi;
2. preservare log, audit, database e file per analisi;
3. revocare sessioni e chiavi API coinvolte;
4. ruotare secret applicativo e credenziali infrastrutturali quando necessario;
5. verificare hash, audit e riferimenti cross-tenant;
6. identificare dati, tenant e intervallo temporale;
7. ripristinare solo da un backup verificato;
8. documentare decisioni e applicare obblighi di notifica con supporto legale/privacy.

## Manutenzione

Il worker elimina periodicamente sessioni scadute, heartbeat vecchi, contatori rate limit, job conclusi oltre retention e file orfani in quarantena. Questa manutenzione non sostituisce metriche, backup o politiche di conservazione approvate.

Eseguire almeno mensilmente aggiornamento dipendenze, `pip-audit`, test completi, prova restore, revisione utenti/chiavi, controllo storage e campionamento di falsi positivi/falsi negativi.
