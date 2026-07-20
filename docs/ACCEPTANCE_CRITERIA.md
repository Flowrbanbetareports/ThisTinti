# Criteri di accettazione — ThisTinti 3.2.0-alpha.1

## Funzionalità del pacchetto

- [x] tenant, utenti, ruoli e sessioni server-side revocabili;
- [x] sospensione tenant con invalidazione immediata degli accessi;
- [x] chiavi API hashate, revocabili e limitate per scope;
- [x] upload e batch sincroni per sviluppo;
- [x] job persistenti asincroni per documenti, batch, rielaborazione e rianalisi;
- [x] quarantena, retry, backoff, lease, heartbeat e recupero job interrotti;
- [x] XML FatturaPA/UBL, P7M, JSON, CSV, XLSX/XLSM e PDF/OCR;
- [x] deduplicazione, parsing atomico e provenienza dei dati;
- [x] catene molti-a-molti e blocco fornitori incompatibili;
- [x] priorità conferma d'ordine → ordine;
- [x] `Decimal`, sconti sequenziali e conversioni unità compatibili;
- [x] blocco confronti tra dimensioni incompatibili;
- [x] anomalie, fascicoli di prova e decisione revisore;
- [x] audit ordinato e verificabile;
- [x] export, backup, verifica e restore;
- [x] Validation Lab e Adaptive Discovery supervisionato;
- [x] dashboard e confronto riga-per-riga;
- [x] OpenAPI e SBOM;
- [x] Proof Graph con contratto delle prove;
- [x] Sentinel con documenti attesi e memoria temporale privata;
- [x] simulazione preventiva con automazione disabilitata senza calibrazione;
- [x] riconciliazione pagamenti e controlli su duplicati/sovrapagamenti;
- [x] process conformance, self-red-team e pattern pack anonimo.

## Sicurezza del pacchetto

- [x] password hashate e token firmati;
- [x] cookie HttpOnly/SameSite, CSRF e controllo origin;
- [x] revoca di sessioni e chiavi API;
- [x] autorizzazione per ruolo e scope;
- [x] tenant isolation applicativa testata;
- [x] PostgreSQL RLS e trigger anti-riferimento cross-tenant;
- [x] parser XML sicuro, limiti OCR e protezioni ZIP/XLSX;
- [x] scanner strutturale e integrazione scanner esterno fail-closed;
- [x] readiness con prova operativa scanner e worker;
- [x] rate limiting condiviso su database;
- [x] audit hash-chain e ricerca segreti nel gate di rilascio;
- [ ] penetration test indipendente completato sul deploy finale;
- [ ] configurazione reverse proxy/TLS finale verificata;
- [ ] processo di firma artefatti del destinatario attivato.

## Qualità interna

- [x] test automatici verdi;
- [x] copertura applicativa almeno 90%;
- [x] Ruff e format puliti;
- [x] Bandit pulito;
- [x] migrazioni upgrade/check/downgrade/upgrade;
- [x] backup/verify/restore nel gate;
- [x] Validation Gate sintetico;
- [x] smoke HTTP;
- [x] OpenAPI senza risposte JSON di successo prive di schema;
- [x] CI PostgreSQL con prova di isolamento;
- [ ] `pip-audit` online eseguito nell'ambiente di rilascio finale;
- [ ] test PostgreSQL/Docker eseguito sull'infrastruttura destinataria.

## Gate esterni

- [ ] pilot autorizzato su documenti reali anonimizzati;
- [ ] falsi positivi e falsi negativi misurati per regola e valore economico;
- [ ] previsioni Sentinel, rischio e confidenza calibrati sul pilot;
- [ ] test di carico, stress e durata;
- [ ] backup e restore provati sull'infrastruttura finale;
- [ ] scanner malware con firme aggiornate e monitorate;
- [ ] privacy, retention, DPA e incident response approvati;
- [ ] integrazione ERP scelta collaudata in staging.

## Criterio corretto di “top”

Il codice può completare il perimetro interno, ma non può auto-certificare dati, infrastruttura o sicurezza indipendente. Il prodotto è production-grade soltanto quando i gate esterni risultano documentati e superati. Nessun numero di test sintetici sostituisce questo passaggio.
