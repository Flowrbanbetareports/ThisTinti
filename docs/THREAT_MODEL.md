# Threat model — ThisTinti 3.4.0-alpha.5

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

Mitigazioni: quarantena, whitelist, limiti, nomi sanitizzati, blocco magic eseguibili, EICAR, scanner esterno, XML senza DTD/entità, P7M verificato, ZIP/XLSX anti-bomb, OCR limitato.

Rischio residuo: vulnerabilità zero-day nel parser/scanner, firme obsolete, file passivo conservato. Isolare worker e scanner e mantenere firme/immagini aggiornate.

### Denial of service

Mitigazioni: rate limiting DB, limiti file/batch/espansione, job asincroni, quote tecniche, lease, retry limitati, timeout OCR/scanner e pids/tmpfs nei container.

Rischio residuo: workload legittimo molto costoso, tenant rumoroso, storage o database saturi. Servono capacity test e quote per piano/tenant sul deploy reale.

### Job duplicati, persi o bloccati

Mitigazioni: idempotency key, stato persistente, lease, heartbeat, backoff, recupero stale e storico errori.

Rischio residuo: effetti esterni futuri non idempotenti. Ogni connettore ERP dovrà implementare riconciliazione e chiavi idempotenti proprie.

### Alterazione silenziosa

Mitigazioni: hash file, vincoli DB, `Decimal`, audit con sequenza canonica e catena hash, manifest backup e prove collegate.

Rischio residuo: un amministratore DB/storage può riscrivere dati e audit. Per garanzie superiori servono log immutabili, firme o ancoraggio esterno.

### Falso risultato economico

Mitigazioni: regole deterministiche, unità compatibili, sconti sequenziali, fonti visibili, Validation Lab, regole apprese sempre confermate, nessuna azione economica automatica.

Rischio residuo: contratti, listini, cambi, eccezioni fiscali o semantica non presenti nei documenti. Necessario pilot reale e revisione umana.

### Supply chain

Mitigazioni: lock, SBOM, CI, Ruff, Bandit, scansione segreti, `pip-audit` bloccante quando la rete è disponibile.

Rischio residuo: l'ambiente locale di generazione non ha potuto interrogare l'indice vulnerabilità per assenza rete; il gate va eseguito nella CI/release environment.

### Perdita dati e backup inutilizzabile

Mitigazioni: backup coerente, hash, verifica, restore protetto, retention e procedure operative.

Rischio residuo: chiavi di cifratura perse, backup non off-site, restore mai provato. La responsabilità resta infrastrutturale.

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

- **configurazione errata dell’operatore**: preflight, segreti separati e avvio fail-closed riducono gli errori, ma non sostituiscono revisione dell’infrastruttura;
- **esposizione accidentale di database o storage**: la rete backplane è interna e soltanto Caddy pubblica porte; fork e override devono essere riesaminati;
- **segreti copiati in immagini o repository**: `.dockerignore`, packaging gate e secret file riducono il rischio; l’operatore deve usare un secret manager adeguato al proprio ambiente;
- **scanner non pronto o firme obsolete**: readiness fallisce se il daemon non risponde, ma età firme e aggiornamenti restano responsabilità operativa;
- **backup sullo stesso host**: lo script crea un archivio verificabile, ma copie off-site, cifratura, retention e prove di restore sono a carico dell’organizzazione;
- **falsa percezione di supporto enterprise**: la configurazione è una reference edition open source, senza hosting, SLA, reperibilità o certificazione.
