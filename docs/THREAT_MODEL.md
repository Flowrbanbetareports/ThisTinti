# Threat model — ThisTinti 3.4.0-alpha.7-rc.15 — Public Preview

RC15 è pubblicata come Public Preview prerelease. Questo threat model descrive controlli e rischi residui del prodotto e della reference edition self-hosted; non sostituisce un penetration test indipendente né una revisione dell'infrastruttura finale.

RC15 mantiene la correzione `pypdf` 6.14.2 → 6.15.0 per `PYSEC-2026-3655` e `PYSEC-2026-3656` introdotta in RC13 e gli hardening successivi su OCR bundled, parsing PDF ambiguo, recupero job, restore e governance degli artefatti. Queste misure riducono rischi noti ma non eliminano il rischio residuo di vulnerabilità future o zero-day nelle librerie che elaborano file non fidati.

## Asset

Documenti originali, dati estratti, relazioni commerciali, anomalie e importi, identità, sessioni, chiavi API, audit, database, storage, quarantena, backup e segreti.

## Confini di fiducia

1. browser o integrazione ↔ API;
2. API/worker ↔ PostgreSQL;
3. API/worker ↔ storage e quarantena;
4. parser/scanner ↔ file non fidato;
5. worker ↔ coda persistente;
6. amministratore ↔ funzioni privilegiate;
7. infrastruttura ↔ backup, log, scanner e secret manager.

## Minacce e mitigazioni

### BOLA/IDOR e contaminazione tra tenant

Mitigazioni: filtri applicativi, contesto tenant per transazione, PostgreSQL Row-Level Security forzata, foreign key e trigger tenant-aware, test API e smoke PostgreSQL CI.

Rischio residuo: privilegi DB con `BYPASSRLS`, migrazioni errate o configurazioni PostgreSQL differenti. Il ruolo applicativo non deve essere owner/superuser e il test va ripetuto sul deploy finale.

### Session hijacking e credenziali macchina

Mitigazioni: sessioni persistenti revocabili, scadenza, `token_version`, `security_version` tenant, revoca su logout/cambio password/ruolo/stato, cookie HttpOnly/SameSite/Secure, CSRF, chiavi API hashate e scope minimi.

Rischio residuo: dispositivo compromesso, secret manager errato, log che catturano il token al momento della creazione.

### Escalation privilegi

Mitigazioni: dipendenze server-side per ruolo/scope, protezione ultimo admin, revoca immediata dopo modifiche, audit e test negativi.

### File malevolo

Mitigazioni: quarantena, whitelist, limiti, nomi sanitizzati, blocco magic eseguibili, EICAR, scanner esterno, XML senza DTD/entità, P7M verificato, ZIP/XLSX anti-bomb, OCR limitato, audit dipendenze e runtime OCR bundled fail-closed nella distribuzione Windows.

Rischio residuo: vulnerabilità zero-day nel parser/scanner, firme obsolete, file passivo conservato. Isolare worker e scanner e mantenere firme/immagini/dipendenze aggiornate.

### Ambiguità o allucinazione nel parsing documentale

Mitigazioni RC15: il solo simbolo `$` non viene promosso automaticamente a USD; righe OCR allineate ma numericamente incoerenti vengono scartate o degradate con revisione umana richiesta; provenienza e confidenza restano esposte. Il workflow di pratica mantiene inoltre espliciti intake, evidenze, decisioni umane e stato economico senza trasformare l'output automatico in una decisione autonoma.

Rischio residuo: documenti scarsamente leggibili, valute implicite, layout non osservati, OCR plausibile ma semanticamente errato o dati contestuali mancanti. L'astensione è preferita alla certezza inventata, ma il pilot reale resta obbligatorio.

### Denial of service

Mitigazioni: rate limiting DB, limiti file/batch/espansione, job asincroni, quote tecniche, lease, retry limitati, timeout OCR/scanner e pids/tmpfs nei container.

Rischio residuo: workload legittimo molto costoso, tenant rumoroso, storage o database saturi. Servono capacity test e quote per piano/tenant sul deploy reale.

### Job duplicati, persi o bloccati

Mitigazioni: idempotency key, stato persistente, lease, heartbeat, backoff, recupero stale e storico errori. Il worker recupera inoltre il job tramite una transazione pulita dopo errori che invalidano la sessione SQLAlchemy, evitando di tentare l'aggiornamento dello stato sulla stessa transazione fallita.

Rischio residuo: effetti esterni futuri non idempotenti. Ogni connettore ERP dovrà implementare riconciliazione e chiavi idempotenti proprie.

### Alterazione silenziosa

Mitigazioni: hash file, vincoli DB, `Decimal`, audit con sequenza canonica e catena hash, manifest backup e prove collegate.

Rischio residuo: un amministratore DB/storage può riscrivere dati e audit. Per garanzie superiori servono log immutabili, firme o ancoraggio esterno.

### Perdita dati e restore parziale

Mitigazioni: backup coerente, hash, verifica e restore protetto. Il database/storage viene preparato in staging prima della sostituzione; il restore SQLite con `--force` sostituisce esattamente lo storage evitando residui, mentre PostgreSQL usa `pg_restore --single-transaction` per limitare stati intermedi lato database.

Rischio residuo: database e filesystem restano risorse distinte e non possono avere atomicità distribuita perfetta senza un coordinatore esterno; restano inoltre rischi da chiavi di cifratura perse, backup non off-site o restore mai provato nell'ambiente definitivo.

### Falso risultato economico

Mitigazioni: regole deterministiche, unità compatibili, sconti sequenziali, fonti visibili, Validation Lab, regole apprese sempre confermate, nessuna azione economica automatica. RC15 separa gravità tecnica, confidenza, esposizione potenziale e perdita confermata e richiede motivazioni per le transizioni di revisione rilevanti.

Rischio residuo: contratti, listini, cambi, eccezioni fiscali o semantica non presenti nei documenti. Necessario pilot reale e revisione umana.

### Supply chain

Mitigazioni: lock, SBOM, CI, Ruff, Bandit, scansione segreti, `pip-audit` bloccante con rete, checksum, provenienza e attestazioni degli artefatti pubblici. I workflow di evidenza non committano direttamente snapshot generati durante la qualificazione del sorgente: le evidenze vengono conservate come artefatti immutabili e i record post-release sono sincronizzati separatamente.

Per RC15 il dependency audit con rete è verde e resta inclusa la correzione `pypdf` che aveva motivato l'hotfix RC13. Il rischio residuo include nuove advisory future, compromissione upstream, dipendenze transitive e strumenti di build; il controllo deve quindi restare continuo per ogni nuova candidata.

## Decisioni deliberate

- nessuna AI remota obbligatoria;
- nessun token in `localStorage` o `sessionStorage`;
- nessuna azione economica irreversibile;
- nessuna auto-attivazione delle regole apprese;
- OCR e dati derivati mantengono provenienza e confidenza;
- produzione fail-closed se mancano PostgreSQL, worker, rate limiting condiviso o scanner operativo.

## Rischi del livello Intelligence 3.2

- **falsa certezza del rischio**: punteggio, confidenza e importo sono spiegati e `safe_to_automate` resta falso senza calibrazione;
- **processo dominante scambiato per regola obbligatoria**: il conformance check segnala deviazioni ma non modifica la contabilità;
- **avvelenamento della memoria privata**: profili e regole apprese richiedono supporto minimo e restano sotto decisione umana;
- **esfiltrazione tramite pattern pack**: nessun dato grezzo, aggregazione dei casi rari e hash delle chiavi dinamiche;
- **self-red-team con effetti collaterali**: gli scenari lavorano su rappresentazioni sintetiche e non mutano documenti o pagamenti;
- **ricevuta OCR interpretata male**: importo con confidenza ridotta, evidenza esplicita e revisione raccomandata.

## Rischi specifici del self-hosted

- **configurazione errata dell’operatore**: preflight, segreti separati e avvio fail-closed riducono gli errori, ma non sostituiscono revisione dell'infrastruttura;
- **esposizione accidentale di database o storage**: la rete backplane è interna e soltanto Caddy pubblica porte; fork e override devono essere riesaminati;
- **segreti copiati in immagini o repository**: `.dockerignore`, packaging gate e secret file riducono il rischio; l’operatore deve usare un secret manager adeguato al proprio ambiente;
- **scanner non pronto o firme obsolete**: readiness fallisce se il daemon non risponde, ma età firme e aggiornamenti restano responsabilità operativa;
- **backup sullo stesso host**: lo script crea un archivio verificabile, ma copie off-site, cifratura, retention e prove di restore sono a carico dell’organizzazione;
- **falsa percezione di supporto enterprise**: la configurazione è una reference edition open source, senza hosting, SLA, reperibilità o certificazione.

## Gate esterno residuo

Il threat model è un documento tecnico interno. Prima di una beta validata o della produzione deve essere confrontato con un penetration test indipendente e con la configurazione effettiva dell'organizzazione. I rilievi critici e alti devono essere corretti e retestati; il documento non va usato come autocertificazione di sicurezza.
