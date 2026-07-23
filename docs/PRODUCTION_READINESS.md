# Production readiness — ThisTinti 3.4.0-alpha.5

## Gate tecnici interni implementati

- suite automatica e copertura minima bloccante;
- Ruff, format, Bandit, compileall e controllo JavaScript;
- migrazioni upgrade/check/downgrade/upgrade;
- Validation Gate sintetico;
- smoke HTTP;
- backup, verifica e restore automatici;
- OpenAPI con schema delle risposte JSON;
- SBOM offline;
- sessioni e chiavi API revocabili;
- coda persistente e worker osservabile;
- readiness fail-closed;
- reference deploy self-hosted con segreti file-based, rete interna, bootstrap offline e accettazione operatore;
- RLS e trigger PostgreSQL inclusi nella migrazione;
- test CI PostgreSQL dedicato ai tentativi cross-tenant;
- harness esterno app/worker con Proof Graph, simulazione, red-team e verifica dopo riavvio;
- rate limiting condiviso;
- scanner malware esterno obbligatorio in produzione;
- calibrazione obbligatoria: pilot reale, almeno 30 scenari, motore corrente e approvazione amministrativa del run esatto prima di abilitare qualunque automazione suggerita dal Sentinel;
- vincoli database e revoca automatica dell'idoneità a ogni nuova validazione.

## Gate esterni obbligatori prima di dati sensibili

### 1. Pilot documentale reale

Usare documenti anonimizzati e autorizzati. Misurare per ogni regola precisione, recall, falsi negativi economici, importo errato e percentuale di casi inviati a revisione. Le metriche sintetiche non possono sostituirlo.

### 2. PostgreSQL e infrastruttura live

Una prova RLS su PostgreSQL cloud Supabase ha già confermato visibilità separata per due tenant e rifiuto di un inserimento cross-tenant con SQLSTATE `42501`. Il workflow `enterprise-self-hosted.yml` è predisposto per costruire e provare l’intero stack Docker dopo la pubblicazione su GitHub. Prima della produzione restano comunque necessari migrazioni, concorrenza, backup, restore e monitoraggio sulla specifica infrastruttura scelta dall’organizzazione.

### 3. Test di carico e durata

Misurare API, coda, worker, OCR, scanner, database e storage con volumi realistici. Definire SLO, capacità, timeout, numero worker e quote tenant.

### 4. Scanner e supply chain

Verificare daemon, aggiornamento firme e tempi di scansione. Eseguire `pip-audit` con rete e bloccare vulnerabilità non accettate. Firmare immagini e artefatti nel processo di rilascio del destinatario.

### 5. Sicurezza indipendente

Eseguire penetration test autenticato e non autenticato, review RLS, gestione segreti, configurazione reverse proxy, CSP/CORS, backup e incident response.

### 6. Privacy e governance

Definire titolarità/responsabilità, basi giuridiche, retention, cancellazione, accessi, localizzazione, DPA, registri e gestione data breach.

### 7. Integrazione operativa

Provare il gestionale/ERP scelto in staging, con idempotenza, retry, riconciliazione e rollback. ThisTinti 3.2 espone chiavi API, job e intelligence spiegabile, ma non dichiara già collaudato uno specifico ERP.

## Criterio di rilascio

La produzione è autorizzabile soltanto quando tutti i gate esterni sono documentati con evidenze, responsabile, data e risultato. Un test verde locale non è sufficiente.
