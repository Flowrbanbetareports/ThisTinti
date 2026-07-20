# ThisTinti 3.1.0 — verifica locale finale

> Documento storico relativo alla release 3.1.0. Per la preview corrente vedere `LOCAL_VERIFICATION_320_ALPHA.md`.


Data: 19 luglio 2026

## Esito

Il gate locale completo della release 3.1.0 si è concluso con exit code 0.

- 100 test superati.
- Copertura del codice applicativo: 91% (soglia minima 90%).
- Ruff: pulito.
- Ruff format: pulito.
- Bandit: pulito.
- Compilazione Python: riuscita.
- JavaScript: sintassi valida.
- Grafo delle dipendenze installate: 61 distribuzioni coerenti.
- Migrazioni: upgrade, check, downgrade completo e nuovo upgrade riusciti.
- Validation Gate sintetico: precisione 1.0, recall 1.0, F1 1.0, MAE 0.
- Smoke HTTP: demo, documenti, catena, casi, readiness e audit riusciti.
- Backup SQLite: creazione, verifica e ripristino riusciti.
- OpenAPI 3.1 rigenerata e verificata: 57 path; nessuna risposta JSON di successo priva di schema.
- SBOM CycloneDX rigenerata: 29 componenti.
- Scansione sorgenti per chiavi esposte, token nel browser e incompatibilità CSP: superata.

## Migliorie principali rispetto alla 3.0.0

- Revoca persistente delle sessioni e invalidazione immediata per utenti o tenant sospesi.
- Ordinamento audit deterministico e migrazione della catena hash.
- Calcoli economici con Decimal, sconti sequenziali e unità di misura normalizzate.
- Conferma d'ordine come baseline commerciale prioritaria.
- Parsing FatturaPA semanticamente più preciso.
- Coda persistente, worker, lease, heartbeat, retry, manutenzione e quarantena.
- Credenziali API revocabili con scope.
- Rate limiting condiviso su database in produzione.
- PostgreSQL Row-Level Security e controlli tenant-aware.
- Separazione fra amministratore PostgreSQL, proprietario delle migrazioni e ruolo runtime.
- Backup e ripristino verificabili.
- Regole scoperte dai dati sempre soggette a conferma umana.

## Gate esterni ancora necessari

Questa verifica non equivale a una certificazione produttiva universale. Prima dell'uso con dati sensibili o decisioni economiche automatiche restano necessari:

- esecuzione della CI con PostgreSQL 16 reale e ruolo runtime non privilegiato;
- scanner malware esterno realmente installato e collegato;
- audit vulnerabilità online delle dipendenze (pip-audit non eseguibile localmente per DNS indisponibile);
- test di carico, stress, durata e ripristino sull'infrastruttura scelta;
- pilot con documenti aziendali reali anonimizzati;
- penetration test indipendente;
- revisione privacy, retention e contrattuale;
- collaudo delle integrazioni ERP effettivamente adottate.

## Valutazione

La release 3.1.0 è idonea a un pilot controllato e tecnicamente più vicina a un prodotto production-grade. Non deve essere descritta come definitivamente certificata finché i gate esterni sopra elencati non producono evidenze verificabili.
