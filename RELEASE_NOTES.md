# 3.4.0-alpha.7-rc.1 — Esperienza iniziale semplificata

- aggiunta un’anteprima visuale utilizzabile prima dell’accesso, senza creare account, caricare file o modificare il database;
- introdotta una guida permanente che spiega il flusso `Carica → Collega → Controlla` con documenti dimostrativi;
- ridotta la navigazione principale a **Inizio**, **Documenti**, **Da controllare** e **Guida**;
- raccolti Collegamenti, Regole proposte, Verifica delle regole, Registro attività e Utenti sotto **Strumenti avanzati**;
- nascosti nella modalità semplice indicatori e pannelli specialistici che non servono al primo utilizzo;
- sostituita la terminologia più tecnica con etichette comprensibili e non autoritative;
- aggiunti test dedicati per progressive disclosure, sicurezza del frontend, piccoli schermi e riduzione del movimento;
- verificati installer Windows, aggiornamento da una precedente alpha, persistenza, disinstallazione, PostgreSQL/RLS e Self-Hosted Reference Edition;
- mantenuto lo stato **Public Preview alpha/RC**: gli output sono informativi e richiedono verifica sui documenti originali.

# 3.4.0-alpha.6-rc.1 — Beta readiness foundation

- introdotto un gate oggettivo che distingue candidata tecnica e beta validata;
- aggiunti audit strutturali di accessibilità con target WCAG 2.2 AA;
- aggiunto un load probe concorrente con report p50/p95/p99 e soglie di regressione;
- aggiunti registro dei gate esterni, pacchetto revisori, piano SLO e runbook di firma;
- predisposta provenienza verificabile per gli artefatti Windows;
- nessuna dichiarazione di beta validata senza pilot reale e revisioni indipendenti.

# 3.4.0-alpha.5 — Identità ThisTinti e motion system accessibile

- sostituito il marchio provvisorio con un monogramma doppia T collegato a un segno di verifica;
- unificati logo applicazione, sito pubblico, favicon e sorgente deterministico dell'icona Windows;
- introdotto un sistema visivo più coerente per accesso, navigazione, card, pipeline, dialoghi e stati operativi;
- aggiunte microanimazioni funzionali e transizioni di pagina comprese fra 150 e 300 ms;
- aggiunto supporto esplicito a `prefers-reduced-motion`, focus visibile e degradazione senza `IntersectionObserver`;
- rinnovata la pagina pubblica con navigazione glass, sezioni progressive e messaggi più precisi sullo stato alpha;
- aggiunti gate automatici per coerenza del logo, validità ICO, JavaScript del sito e accessibilità del movimento;
- nessuna modifica ai limiti operativi: risultati da verificare, nessuna decisione economica automatica e installer ancora non firmato.

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
