# ThisTinti

ThisTinti è una piattaforma locale e configurabile per collegare documenti, verificarne la coerenza, evidenziare possibili differenze e mostrare le prove consultabili che hanno generato ogni segnalazione.

ThisTinti non decide, non approva e non certifica nulla. Organizza informazioni e possibili incongruenze; l’organizzazione stabilisce come utilizzarle e resta responsabile delle proprie procedure.

## Stato del rilascio

Release pubblica corrente: **3.4.0-alpha.7-rc.15 — RC15 Pilot-Ready — Public Preview**.

RC15 completa il workflow supervisionato di pratica, il lifecycle auditabile delle segnalazioni, il pilot workspace integrato, il profilo azienda versionato e le operazioni esplicite di export, archivio e cancellazione. La pubblicazione è legata al commit applicativo, al tree Git e al workflow Windows verificati qui sotto.

RC15 resta una Public Preview supervisionata. I gate tecnici automatici e il ciclo Windows RC14→RC15 sono stati superati, ma questo non chiude i gate esterni necessari per una beta validata o per la produzione: pilot reale autorizzato, revisione indipendente di sicurezza e legale/privacy/trademark, collaudo WCAG manuale con tecnologie assistive, test con utenti non istruiti, firma Authenticode e prove sull’infrastruttura definitiva restano separati e devono produrre evidenza reale.

Evidenza della Public Preview RC15:

- tag: `v3.4.0-alpha.7-rc.15`;
- commit applicativo: `0c99155d17374ce195db4ec65200a8edcf1bcdd1`;
- tree Git: `8e91471fbaa833c10011e1863cd0049740c64225`;
- workflow Windows: run `33125242692`, build `513`;
- installer: `ThisTinti-Setup-3.4.0-alpha.7-rc.15-x64.exe`;
- SHA-256 installer: `48429173e92ff189d1d968609749695a8ac9354519710850e61fd954c7d9c832`;
- pubblicazione GitHub: `2026-08-27T23:32:18Z`;
- release: https://github.com/Flowrbanbetareports/ThisTinti/releases/tag/v3.4.0-alpha.7-rc.15

## Identità e posizionamento

Il nome ufficiale del progetto è **ThisTinti**. `Flowrbanbetareports` è soltanto l'account tecnico GitHub che ospita il repository e non costituisce un secondo marchio o una parte del prodotto.

Nel periodo alpha ThisTinti resta open source, gratuito, local-first e destinato a demo e pilot supervisionati. Non viene offerto come SaaS o servizio gestito. Decisioni, manutenzione, canali ufficiali e gate produttivi sono definiti in `GOVERNANCE.md`, `ROADMAP.md` e `docs/ROADMAP_TO_1_0.md`.

## Download locale gratuito

La Local Edition è progettata per essere usata senza un servizio gestito da ThisTinti:

- nessun account centrale e nessun cloud obbligatorio;
- nessuna telemetria e nessun documento inviato all'autore;
- database, file e backup conservati sul computer dell'organizzazione;
- launcher che avvia automaticamente API e worker e apre il browser;
- installer Windows per utente singolo, senza privilegi amministrativi;
- archivio portable e checksum SHA-256;
- sorgente corrispondente incluso ed esportabile sotto licenza Apache 2.0.

Installer Windows RC15 verificato:

https://github.com/Flowrbanbetareports/ThisTinti/releases/download/v3.4.0-alpha.7-rc.15/ThisTinti-Setup-3.4.0-alpha.7-rc.15-x64.exe

La build pubblica viene generata da `.github/workflows/windows-release.yml`. Prima della pubblicazione il percorso di rilascio esegue test, controlli di sicurezza, build congelata, installazione della baseline, aggiornamento, persistenza dei dati, smoke test dell’app installata, Diagnostica reale, disinstallazione, checksum, provenienza e attestazioni.

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

## Governance dell’automazione

I dataset reali sono accettati come `anonymized_pilot` o `production` soltanto con almeno 30 scenari, autorizzazione esplicita, perimetro documentato, ground truth e due revisori distinti. Prima del caricamento possono essere controllati con `python scripts/validate_pilot_dataset.py pilot.json`; ogni run può esportare un rapporto redatto JSON o Markdown.

Il Validation Gate sintetico serve soltanto alla regressione tecnica e non può abilitare automazioni economiche. Le azioni economiche restano sotto controllo umano.

## Capacità principali

- tenant, utenti, ruoli, sessioni revocabili e chiavi API con scope;
- upload singolo e batch, quarantena e worker persistente con retry;
- FatturaPA, P7M, UBL/Peppol, JSON, CSV, XLSX/XLSM e PDF con OCR locale;
- documenti `proposal`, `order`, `confirmation`, `delivery`, `invoice`, `payment`, `return`, `credit_note`;
- matching molti-a-molti e calcoli economici `Decimal`;
- Proof Graph con collegamenti, forza delle evidenze e campi in conflitto;
- controllo dei documenti attesi e riconciliazione fattura–pagamento;
- sovrapagamenti, pagamenti orfani e possibili duplicati;
- controllo incrociato tra estrazione, aritmetica e coerenza dei collegamenti;
- correzione supervisionata con audit e rianalisi;
- fascicoli di prova, revisione umana e catena hash dell’audit;
- Adaptive Discovery con regole apprese sempre soggette a conferma;
- Validation Lab, backup/restore, PostgreSQL RLS, rate limiting condiviso, OpenAPI e SBOM;
- diagnostica locale integrata con esiti espliciti e verbale JSON scaricabile.

## Avvio locale da sorgente

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

Per usare il percorso asincrono raccomandato:

```env
THISTINTI_ASYNC_INGESTION_ENABLED=true
THISTINTI_ALLOW_SYNCHRONOUS_INGESTION=false
```

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
python scripts/run_worker.py --poll-seconds 1
```

## Docker e PostgreSQL

```bash
cp .env.docker.example .env
# Sostituire password e segreto; configurare uno scanner reale per produzione.
docker compose up --build
```

Il compose incluso è una base di deploy, non una certificazione dell'infrastruttura. Per un ambiente produttivo servono configurazione, responsabilità operative e prove esterne specifiche.

## Backup e ripristino

```bash
python scripts/backup_system.py /backup/thistinti-$(date +%F).zip
python scripts/verify_backup.py /backup/thistinti-2026-08-26.zip
python scripts/restore_backup.py /backup/thistinti-2026-08-26.zip \
  --sqlite-database /restore/thistinti.db \
  --storage-dir /restore/data
```

Per PostgreSQL vengono usati `pg_dump` e `pg_restore`. Conservazione, disinstallazione e cancellazione completa sono descritte in `docs/DATA_LIFECYCLE.md`.

## Verifica del rilascio

```bash
make verify
# oppure
python scripts/verify_release.py
```

La verifica comprende lint, format, Bandit, compileall, JavaScript, test, copertura minima, dipendenze dichiarate, migrazioni upgrade/downgrade, Validation Gate, smoke HTTP, backup/verify/restore, SBOM, OpenAPI e ricerca di segreti/token browser storage. `pip-audit` è bloccante in CI quando è disponibile la rete.

La verifica automatica non sostituisce pilot reali, penetration test indipendente, revisione professionale legale/privacy, collaudo con tecnologie assistive o firma Authenticode.

## Uso responsabile e condizioni

Prima dell'uso leggere `TERMS_OF_USE.md`, `DISCLAIMER.md`, `PRIVACY.md` e `TRADEMARKS.md`. Gli output sono indicativi e devono essere verificati sui documenti originali.

ThisTinti non invia contestazioni, non esegue o blocca pagamenti reali, non modifica la contabilità e non decide autonomamente se pagare una fattura. Il sistema prepara evidenze e raccomandazioni; le azioni economiche restano sotto controllo umano.

## Documentazione

- `GOVERNANCE.md`: identità, obiettivo, canali ufficiali e processo decisionale;
- `ROADMAP.md`: stato corrente e priorità;
- `docs/ROADMAP_TO_1_0.md`: criterio di completamento e percorso dalla Public Preview alla 1.0 Stable;
- `docs/RC13_SECURITY_CANDIDATE.md`: motivazione, promozione ed evidenza storica dell’hotfix RC13;
- `docs/RC13_HANDS_ON_ACCEPTANCE.md`: protocollo di collaudo umano end-to-end della RC13;
- `docs/PUBLIC_LAUNCH_CHECKLIST.md`: stato tecnico e gate esterni;
- `docs/NAME_AND_DOMAIN_CLEARANCE.md`: verifica del nome e del dominio prima di usi commerciali o produttivi;
- `docs/LICENSE_REVIEW.md`: inventario e revisione delle licenze/distribuzione;
- `docs/BETA_READINESS_STATUS.md`: distinzione tra Public Preview, beta tecnica e beta validata;
- `docs/USER_GUIDE_SIMPLE.md`: guida essenziale per nuovi utenti;
- `docs/PILOT_KIT.md`: materiale per pilot controllati;
- `docs/LOCAL_EDITION.md`: installazione e gestione della Local Edition;
- `docs/DATA_LIFECYCLE.md`: conservazione e cancellazione dati;
- `SECURITY.md`: controlli e segnalazione responsabile;
- `RELEASE_NOTES.md`: cronologia delle release.
