# ThisTinti

ThisTinti è una piattaforma locale e configurabile per collegare documenti, verificarne la coerenza, evidenziare possibili differenze e mostrare le prove consultabili che hanno generato ogni segnalazione.

ThisTinti non decide, non approva e non certifica nulla. Organizza informazioni e possibili incongruenze; l’organizzazione stabilisce come utilizzarle e resta responsabile delle proprie procedure.

## Stato del rilascio

Versione: **3.4.0-alpha.7-rc.3 — Public Preview con primo accesso locale corretto**.

Questa preview conserva il motore documentale esistente e offre due distribuzioni gratuite: una Local Edition per singola postazione e una Self-Hosted Reference Edition con PostgreSQL, worker scalabili, TLS, scanner malware e strumenti operativi per team tecnici.

La candidata è adatta a sviluppo, dimostrazioni e **pilot controllati con documenti autorizzati e anonimizzati**. L’interfaccia iniziale presenta soltanto Inizio, Documenti, Da controllare e Guida; gli strumenti specialistici restano disponibili tramite progressive disclosure. Nella RC3 il launcher riconosce se lo spazio locale deve essere creato o se esiste già e apre il percorso corretto; il menu laterale resta indipendentemente scorrevole sui display con altezza ridotta. La beta validata richiede ancora pilot reale e revisioni indipendenti.

## Identità e posizionamento

Il nome ufficiale del progetto è **ThisTinti**. `Flowrbanbetareports` è soltanto l'account tecnico GitHub che ospita il repository e non costituisce un secondo marchio o una parte del prodotto.

Nel periodo alpha ThisTinti resta open source, gratuito, local-first e destinato a demo e pilot supervisionati. Non viene offerto come SaaS o servizio gestito. Decisioni, manutenzione, canali ufficiali e gate produttivi sono definiti in `GOVERNANCE.md` e `ROADMAP.md`.

## Download locale gratuito

La Local Edition è progettata per essere usata senza un servizio gestito da ThisTinti:

- nessun account centrale e nessun cloud obbligatorio;
- nessuna telemetria e nessun documento inviato all'autore;
- database, file e backup conservati sul computer dell'azienda;
- launcher che avvia automaticamente API e worker e apre il browser;
- installer Windows per utente singolo, senza privilegi amministrativi;
- archivio portable e checksum SHA-256;
- sorgente corrispondente incluso ed esportabile sotto licenza Apache 2.0.

La build pubblica viene generata da `.github/workflows/windows-release.yml`. Prima di pubblicare un tag, il workflow esegue test, controlli di sicurezza e uno smoke test sull'eseguibile congelato che comprende caricamento, worker, arresto, riavvio e persistenza. Vedere `docs/LOCAL_EDITION.md` e `docs/RELEASE_AUTHENTICITY.md`.

## Self-Hosted Reference Edition gratuita

Per organizzazioni dotate di personale tecnico è disponibile `deploy/enterprise/docker-compose.enterprise.yml`. La configurazione include PostgreSQL, worker replicabili, Caddy, ClamAV, segreti locali, bootstrap offline del primo amministratore, backup e ripristino.

Non è un servizio gestito, non include SLA o supporto garantito e non viene amministrato dall'autore. L'organizzazione o il fornitore da essa scelto è responsabile di infrastruttura, dati, privacy, sicurezza, costi, aggiornamenti, monitoraggio e incidenti.

```bash
python scripts/enterprise_init.py \
  --host thistinti.example.com \
  --accept-operator-responsibility \
  --accept-no-support
python scripts/enterprise_preflight.py --directory deploy/enterprise
```

Vedere `docs/ENTERPRISE_SELF_HOSTED.md`, `docs/RESPONSIBILITY_MATRIX.md` e `docs/ENTERPRISE_ACCEPTANCE_CHECKLIST.md`.

### Governance dell'automazione

I dataset reali sono accettati come `anonymized_pilot` o `production` soltanto con almeno 30 scenari, autorizzazione esplicita, perimetro documentato, ground truth e due revisori distinti. Prima del caricamento possono essere controllati con `python scripts/validate_pilot_dataset.py pilot.json`; ogni run può esportare un rapporto redatto JSON o Markdown.

Il Validation Gate sintetico serve soltanto alla regressione tecnica e non può abilitare automazioni. `safe_to_automate` può diventare vero soltanto quando esiste un dataset `anonymized_pilot` o `production`, composto da almeno 30 scenari, eseguito con la versione corrente del motore e approvato esplicitamente da un amministratore sullo specifico run. Ogni nuova esecuzione sul dataset revoca l'idoneità precedente fino a una nuova revisione. Vincoli equivalenti sono applicati anche dal database.

## Capacità principali

- tenant, utenti, ruoli, sessioni revocabili e chiavi API con scope;
- upload singolo e batch, quarantena e worker persistente con retry;
- FatturaPA, P7M, UBL/Peppol, JSON, CSV, XLSX/XLSM e PDF con OCR locale;
- documenti `proposal`, `order`, `confirmation`, `delivery`, `invoice`, `payment`, `return`, `credit_note`;
- ricevute PDF di pagamento con riconoscimento prudente dell'importo;
- matching molti-a-molti e calcoli economici `Decimal`;
- **Proof Graph**: grafo delle prove, collegamenti, forza delle evidenze e campi in conflitto;
- **Sentinel Twin**: documenti attesi, scadenze generiche o apprese dallo storico privato del fornitore;
- **simulazione preventiva**: rischio e importo potenzialmente esposto prima di approvare fattura, pagamento o consegna;
- riconciliazione fattura–pagamento, sovrapagamenti, pagamenti orfani e possibili duplicati;
- **tripla verifica** tra estrazione, controllo aritmetico e coerenza del grafo;
- **process conformance** leggero per confrontare una pratica con il percorso dominante dell'azienda;
- **self-red-team** manuale o persistente, senza alterare i documenti originali;
- memoria privata e pattern anonimi con soglia minima, senza documenti, nomi, importi o riferimenti;
- fascicoli di prova, revisione umana, audit con sequenza canonica e catena hash;
- Adaptive Discovery con regole apprese sempre soggette a conferma;
- Validation Lab, backup/restore, PostgreSQL RLS, rate limiting condiviso, OpenAPI e SBOM.

## Avvio locale

Requisiti: Python 3.11–3.13. Node.js è necessario solo per il controllo sintattico del frontend. Per OCR servono Poppler e Tesseract.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python scripts/generate_secret.py
# Inserire il segreto generato in .env
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Aprire `http://127.0.0.1:8000`, creare il primo tenant e usare **Carica esempio**.

## Elaborazione asincrona

Per usare il percorso raccomandato anche localmente:

```env
THISTINTI_ASYNC_INGESTION_ENABLED=true
THISTINTI_ALLOW_SYNCHRONOUS_INGESTION=false
```

Avviare API e worker in processi separati:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
python scripts/run_worker.py --poll-seconds 1
```

I documenti vengono prima salvati in quarantena. Il worker li scansiona, analizza e trasferisce nello storage definitivo. Gli endpoint `/api/jobs/*` espongono stato, errori, tentativi e cancellazione.

## Docker e PostgreSQL

```bash
cp .env.docker.example .env
# Sostituire password e segreto; configurare lo scanner esterno per produzione.
docker compose up --build
```

Il servizio `migrate` applica Alembic una sola volta; `app` e `worker` partono separatamente. In produzione sono obbligatori PostgreSQL, HTTPS, registrazione pubblica disabilitata, ingestion asincrona, rate limiting DB e scanner malware operativo.

Il compose incluso è una base di deploy, non una certificazione dell'infrastruttura. Lo scanner esterno deve essere installato o fornito dall'ambiente e il comando indicato da `THISTINTI_MALWARE_SCANNER_COMMAND` deve eseguire una scansione reale.

## Backup e ripristino

```bash
python scripts/backup_system.py /backup/thistinti-$(date +%F).zip
python scripts/verify_backup.py /backup/thistinti-2026-07-19.zip
python scripts/restore_backup.py /backup/thistinti-2026-07-19.zip \
  --sqlite-database /restore/thistinti.db \
  --storage-dir /restore/data
```

Per PostgreSQL vengono usati `pg_dump` e `pg_restore`. Il backup contiene manifest, versione, hash dei componenti e copia dello storage; il restore rifiuta sovrascritture implicite. Conservazione, disinstallazione e cancellazione completa sono descritte in `docs/DATA_LIFECYCLE.md`.

## Verifica del rilascio

```bash
make verify
# oppure
python scripts/verify_release.py
```

La verifica esegue lint, format, Bandit, compileall, JavaScript, test, copertura minima 90%, dipendenze dichiarate, migrazioni upgrade/downgrade, Validation Gate, smoke HTTP, backup/verify/restore, SBOM, OpenAPI e ricerca di segreti/token browser storage.

`pip-audit` resta bloccante in CI quando è disponibile la rete. La verifica locale non può sostituire PostgreSQL live, load test, scanner reale o penetration test.

## Verifica esterna gratuita

Il workflow `.github/workflows/ci.yml` include una prova cloud a costo zero su runner GitHub effimero con PostgreSQL 16, ruoli owner/runtime separati, migrazioni Alembic, RLS, app, worker, ingestione asincrona e verifica della persistenza dopo il riavvio. Le evidenze vengono caricate come artifact temporaneo di GitHub Actions.

Il comando usato dalla prova è riutilizzabile anche su uno staging proprio:

```bash
python scripts/external_cloud_proof.py bootstrap --state evidence/state.json --report evidence/report.json
# riavviare app e worker
python scripts/external_cloud_proof.py verify --state evidence/state.json --report evidence/report.json
```

Una prova PostgreSQL/RLS separata è già stata eseguita sul progetto Supabase gratuito dedicato `thistinti-staging`: ciascun tenant ha visto soltanto la propria riga e un inserimento cross-tenant è stato rifiutato con SQLSTATE `42501`. La prova completa dell'app su GitHub Actions richiede che il repository venga pubblicato tramite un account GitHub autenticato.

## Uso responsabile e condizioni

Prima dell'uso leggere `TERMS_OF_USE.md`, `DISCLAIMER.md`, `PRIVACY.md` e `TRADEMARKS.md`. La distribuzione ufficiale richiede una doppia conferma nell'installer e al primo avvio. Gli output sono indicativi e devono essere verificati sui documenti originali.

## Confini deliberati

ThisTinti non invia contestazioni, non esegue o blocca pagamenti reali, non modifica la contabilità e non decide autonomamente se pagare una fattura. Non tratta una regola appresa come verità solo perché ha confidenza elevata. Il sistema prepara evidenze e raccomandazioni; le azioni economiche restano sotto controllo umano.

## Documentazione

- `GOVERNANCE.md`: identità, obiettivo, canali ufficiali e processo decisionale;
- `ROADMAP.md`: priorità dalla alpha alla preparazione operativa;
- `TERMS_OF_USE.md`: condizioni, rischi, responsabilità e approvazione specifica;
- `DISCLAIMER.md`: avviso essenziale;
- `PRIVACY.md`: dati locali e responsabilità dell'organizzazione;
- `TRADEMARKS.md`: uso del nome e versioni modificate;
- `SECURITY.md`: controlli, versioni supportate e segnalazione responsabile;
- `docs/LOCAL_EDITION.md`: installazione, dati locali, backup e distribuzione gratuita;
- `docs/DATA_LIFECYCLE.md`: conservazione, disinstallazione e cancellazione completa;
- `docs/PUBLIC_LAUNCH_CHECKLIST.md`: gate manuali e tecnici prima di ogni pubblicazione;
- `docs/NAME_AND_DOMAIN_CLEARANCE.md`: stato delle verifiche preliminari su nome e dominio;
- `docs/USER_GUIDE_SIMPLE.md`: guida essenziale destinata ai nuovi utenti;
- `docs/PILOT_KIT.md`: perimetro e materiale per pilot controllati;
- `docs/LICENSE_REVIEW.md`: revisione delle licenze e dei componenti distribuiti.
