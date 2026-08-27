# Production readiness — ThisTinti 3.4.0-alpha.7-rc.14 — Public Preview, non produzione

RC14 è pubblicata e verificabile come Public Preview. Questo documento elenca ciò che esiste tecnicamente e ciò che manca per un uso produttivo: la pubblicazione della prerelease non autorizza né implica la produzione.

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
- harness esterno app/worker con grafo delle evidenze, stima euristica, scenari sintetici di errore e verifica dopo riavvio;
- rate limiting condiviso;
- scanner malware esterno obbligatorio in produzione;
- calibrazione obbligatoria: pilot reale, almeno 30 scenari, motore corrente e approvazione amministrativa del run esatto prima di abilitare qualunque automazione suggerita dai controlli temporali;
- vincoli database e revoca automatica dell'idoneità a ogni nuova validazione;
- diagnostica locale integrata con verbale scaricabile; non sostituisce i gate esterni;
- ciclo Windows RC14 verificato sul commit applicativo `6bbb980256869896bf66f0e125ccff6c047540e3` con Windows run `33104580870` / build `477`;
- aggiornamento Windows RC14 verificato anche con la precedente alpha in esecuzione, inclusi chiusura del vecchio processo, smoke della versione aggiornata, diagnostica, disinstallazione e conservazione dei dati;
- dependency audit RC14 verde; resta inclusa la correzione `pypdf` 6.14.2 → 6.15.0 per `PYSEC-2026-3655` e `PYSEC-2026-3656` introdotta in RC13;
- hardening RC14 di backup/restore, worker recovery, OCR bundled fail-closed, parser PDF conservativo e governance degli artefatti CI.

## Gate esterni obbligatori prima di dati sensibili in produzione

### 1. Pilot documentale reale

Usare documenti anonimizzati e autorizzati. Misurare per ogni regola precisione, recall, falsi negativi economici, importo errato e percentuale di casi inviati a revisione. Le metriche sintetiche o controllate non possono sostituirlo.

### 2. PostgreSQL e infrastruttura live

Le prove PostgreSQL e self-hosted automatiche verificano separazione tenant, RLS, backup e persistenza nella reference edition. Prima della produzione restano necessari migrazioni, concorrenza, backup, restore, monitoraggio e capacità sulla specifica infrastruttura scelta dall’organizzazione.

### 3. Test di carico e durata

Misurare API, coda, worker, OCR, scanner, database e storage con volumi realistici. Definire SLO, capacità, timeout, numero worker e quote tenant.

### 4. Scanner e supply chain

Verificare daemon, aggiornamento firme e tempi di scansione. Eseguire `pip-audit` con rete e bloccare vulnerabilità non accettate. Gli artefatti pubblici RC14 hanno checksum, provenienza e attestazioni, ma la firma Authenticode resta un gate separato.

### 5. Sicurezza indipendente

Eseguire penetration test autenticato e non autenticato, review RLS, gestione segreti, configurazione reverse proxy, CSP/CORS, backup e incident response. Chiudere e retestare i rilievi critici/alti.

### 6. Privacy, legale e governance

Definire titolarità/responsabilità, basi giuridiche, retention, cancellazione, accessi, localizzazione, DPA, registri e gestione data breach. Sottoporre condizioni, privacy, licenze e nome/marchio a revisione professionale nel perimetro giuridico effettivo.

### 7. Accessibilità e onboarding reale

Eseguire collaudo manuale WCAG 2.2 AA con tastiera e tecnologie assistive e sessioni osservate con utenti non istruiti. I controlli automatici di struttura, reflow e Chromium non sono una certificazione professionale.

### 8. Firma Windows

Gli installer destinati a utenti non tecnici devono essere firmati con certificato Authenticode valido, timestampati e verificati su Windows pulito. La chiave privata non deve essere salvata nel repository.

### 9. Integrazione operativa

Provare il gestionale/ERP scelto in staging, con idempotenza, retry, riconciliazione e rollback. ThisTinti espone chiavi API, job e intelligence spiegabile, ma non dichiara già collaudato uno specifico ERP.

## Criterio di rilascio

La produzione / 1.0 Stable è autorizzabile soltanto quando tutti i gate esterni applicabili sono documentati con evidenze, responsabile, data e risultato, e i rischi residui sono formalmente accettati dall’organizzazione responsabile. Una Public Preview o un test verde locale non sono sufficienti.
