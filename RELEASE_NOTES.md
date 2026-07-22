# 3.4.0-alpha.4 — Windows validation and public alpha

- installer avviato e verificato su un PC Windows 11 reale, incluso il comportamento previsto di Microsoft Defender SmartScreen per un binario non firmato;
- corretta la schermata di creazione dello spazio e verificata la creazione del primo amministratore;
- sostituita la precedente icona a T con il marchio ThisTinti a collegamenti documentali e rombo di verifica;
- aggiunti test automatici per caricamento dimostrativo, esportazione, persistenza dopo riavvio, installazione silenziosa, aggiornamento e disinstallazione con conservazione dei dati;
- confermati i gate CI, PostgreSQL/RLS, Docker enterprise, backup e ripristino;
- release ancora alpha, non firmata digitalmente e destinata a valutazione e pilot controllati con verifica umana.

# 3.4.0-alpha.3 — Rebranding preliminare a ThisTinti

- Ridenominazione completa del nome precedente a ThisTinti prima del lancio pubblico.
- Pacchetto Python, installer, eseguibili, variabili, URL, documentazione, SBOM e controlli aggiornati.
- Nessuna compatibilità pubblica da preservare: le versioni precedenti erano alpha non distribuite.
- Clearance del nome ancora preliminare: prima dell'acquisto del dominio restano la verifica live presso il registrar e, per maggiore tutela, una ricerca professionale sui marchi simili.

# 3.4.0-alpha.3 — Public launch preparation

- aggiunte clearance preliminare di nome e dominio;
- aggiunte guida semplice, kit pilot e checklist di pubblicazione;
- aggiunti brief per revisione legale e security review;
- aggiunta revisione preliminare delle licenze;
- aggiunto gate automatico di readiness;
- sito ampliato con documentazione, limiti e stato alpha.

# 3.4.0-alpha.1 — Self-Hosted Reference Edition preview

- deploy Docker Compose separato con PostgreSQL, worker scalabili, Caddy e ClamAV;
- segreti basati su file e inizializzazione locale fail-closed;
- accettazione dell’operatore registrata localmente e verificata a ogni avvio production;
- registrazione pubblica disabilitata e bootstrap offline del primo amministratore;
- rete interna per database, worker e scanner; solo il proxy espone HTTP/HTTPS;
- backup PostgreSQL + storage e ripristino esplicito;
- preflight automatico, checklist di accettazione e matrice delle responsabilità;
- nessun servizio gestito, SLA o supporto implicito.

# 3.3.0-alpha.2 — Legal hardening preview

- versioned and hashed local legal acceptance;
- separate approval of relevant clauses in installer and first run;
- server-side acceptance check for Local Edition registration;
- persistent in-app risk notice and legal page;
- download gate and legal notice in GitHub Releases;
- clarified local privacy, no support/SLA, third-party modification and trademark boundaries.

# 3.3.0-alpha.1 — Local Free Edition preview

- distribuzione locale senza account centrale, telemetria o cloud obbligatorio;
- launcher grafico che gestisce server e worker;
- cartella dati separata dall'installazione e conservata alla disinstallazione;
- backup automatico del database prima delle migrazioni;
- renderer PDFium integrato e supporto a Tesseract locale;
- sorgente corrispondente incluso ed esportabile;
- licenza Apache 2.0, NOTICE e piano di free download;
- build Windows PyInstaller + Inno Setup con installer, portable ZIP e SHA-256;
- smoke test end-to-end della distribuzione con persistenza dopo riavvio.

La release resta `alpha`: il pacchetto Windows deve essere generato e provato su macchine Windows reali prima di essere indicato come stabile. Non è firmato digitalmente e può attivare SmartScreen.

# ThisTinti 3.2.0-alpha.1 — Proof Graph & Sentinel preview

## Direzione del prodotto

La 3.2 trasforma ThisTinti da controllore documentale reattivo a sistema preventivo e spiegabile. La release è una preview da pilot: non esegue azioni economiche, ma ricostruisce le prove, prevede ciò che manca e simula il rischio prima dell'approvazione.

## Novità

- nuovi ruoli documento `proposal` e `payment`;
- Proof Graph con nodi, relazioni, confidenza e forza delle evidenze;
- documenti attesi e scadenze apprese dallo storico privato dopo supporto minimo;
- simulazione di approvazione con punteggio, decisione e importo a rischio;
- riconciliazione pagamenti, sovrapagamenti, pagamenti orfani e duplicati;
- tripla verifica fra estrazione, aritmetica e coerenza del grafo;
- process conformance rispetto al percorso dominante del tenant/fornitore;
- self-red-team manuale e tramite job persistente;
- pattern pack anonimo con aggregazione dei casi rari;
- riconoscimento prudente dell'importo da ricevute PDF di pagamento;
- fatture di servizi non vengono trattate come merce fisica senza evidenza positiva;
- pagamenti dello stesso importo senza riferimento comune non sono considerati automaticamente duplicati;
- esposizione economica non duplicata e blocco delle simulazioni senza documento oggetto;
- interfaccia con rischio, aspettative, simulazione e red-team;
- prova cloud aggiornata per proposta, fattura, pagamento, intelligence e persistenza.

## Sicurezza e prudenza

- nessuna automazione è dichiarata sicura senza pilot reale, almeno 30 scenari, motore corrente e approvazione amministrativa dello specifico run;
- il Validation Gate sintetico non può mai autorizzare automazioni; una nuova esecuzione revoca l'approvazione precedente;
- vincoli database impediscono dataset sintetici idonei e run approvati senza autore, data e motivazione;
- le nuove regole restano supervisionate;
- self-red-team non altera i documenti;
- il pattern pack non esporta documenti, nomi, importi, date o identificativi;
- downgrade bloccato se sono ancora presenti documenti o job incompatibili con la 3.1.

## Limiti dichiarati

La preview non include ancora un secondo modello multimodale indipendente né federated learning crittografico. Queste sono estensioni architetturali future, non capacità già certificate.

---

# ThisTinti 3.1.0 — hardening e production foundation

## Correzioni critiche

- logout con revoca immediata della sessione bearer e cookie;
- invalidazione delle sessioni dopo sospensione tenant, cambio ruolo, disattivazione o cambio password;
- controllo corretto dei totali dichiarati pari a zero;
- blocco dei collegamenti manuali tra fornitori differenti;
- ordinamento audit canonico tramite `sequence_no`, anche con timestamp identici;
- utilizzo della conferma d'ordine come fonte commerciale prioritaria rispetto all'ordine;
- ricostruzione reversibile della catena audit durante la migrazione.

## Motore economico

- precisione `Decimal` nel parsing e nelle regole;
- applicazione sequenziale degli sconti;
- riferimenti FatturaPA letti dalla sezione semantica corretta;
- quantità e prezzi canonici per unità compatibili;
- conversioni massa, volume, lunghezza, area, tempo e unità singole;
- anomalia esplicita `unit_mismatch` e soppressione dei confronti economici ingannevoli;
- firme duplicate e confronti tra documenti normalizzati per unità.

## Elaborazione e affidabilità

- coda persistente per documento, batch, rielaborazione e rianalisi;
- quarantena, cartella rifiutati e scansione prima dell'ingestione;
- worker separato con lease, heartbeat, retry, backoff e recupero lavori bloccati;
- idempotenza delle richieste asincrone;
- retention di sessioni, job, heartbeat, contatori rate limit e file orfani;
- disattivazione degli endpoint sincroni in produzione.

## Sicurezza e multi-tenant

- PostgreSQL Row-Level Security forzata sulle entità aziendali;
- contesto tenant riapplicato a ogni nuova transazione;
- trigger DB contro riferimenti cross-tenant;
- chiavi API mostrate una sola volta, hashate, revocabili e limitate per scope;
- rate limiting atomico su database per deploy multiistanza;
- scanner malware obbligatorio e sondato con una scansione reale dalla readiness;
- configurazione production fail-closed;
- ruolo processo separato per app, worker e migrazioni.

## Operazioni e integrazioni

- backup coerente SQLite/PostgreSQL con manifest e SHA-256;
- verifica archivio e restore protetto da sovrascrittura;
- worker e migrazione separati nel compose;
- endpoint worker, sessioni, chiavi API e job;
- OpenAPI ripulito: nessuna risposta JSON di successo priva di schema;
- readiness estesa a database, storage, OCR, scanner e heartbeat worker;
- request ID e `Server-Timing`.

## Discovery

Le regole create dai dati non vengono più auto-attivate. Anche sopra soglia richiedono una decisione umana. L'auto-attivazione resta ammessa soltanto per controlli predefiniti, deterministici e sufficientemente supportati.

## Compatibilità

- migrazione Alembic reversibile da 3.0.0;
- endpoint sincroni mantenuti per sviluppo e compatibilità, ma disattivabili;
- SQLite mantenuto per test e uso locale;
- PostgreSQL richiesto in produzione.

## Zero-cost cloud proof hardening

- workflow GitHub Actions separato con PostgreSQL 16 e ruoli least-privilege;
- prova automatica app + worker, ingestione asincrona, riavvio e persistenza;
- report JSON e log caricati come artifact temporaneo;
- policy RLS ottimizzata con init plan per il contesto tenant;
- runner di test/copertura e gate Python con terminazione deterministica;
- prova RLS esterna completata sul progetto Supabase gratuito dedicato.

## Gate esterni non dichiarati come superati

La release non afferma di avere completato: pilot su documenti reali, test di carico sull'infrastruttura finale, scansione vulnerabilità online nell'ambiente locale, collaudo completo dell'app su PostgreSQL cloud, penetration test indipendente, revisione GDPR/contrattuale o integrazione con uno specifico ERP.
