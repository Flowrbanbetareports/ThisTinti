# ThisTinti 3.2.0-alpha.1 — rapporto conclusivo di verifica

Data di congelamento: 20 luglio 2026.

## Esito

La preview Proof Graph & Sentinel ha superato tutti i gate locali e le prove esterne gratuite disponibili prima della pubblicazione del repository.

- 121 test superati;
- copertura applicativa complessiva: 91% (soglia bloccante: 90%);
- Ruff, controllo di formattazione, Bandit, compilazione Python e sintassi JavaScript superati;
- 61 distribuzioni del grafo dipendenze installato validate;
- migrazioni Alembic: upgrade completo, controllo schema, downgrade fino alla base e nuovo upgrade riusciti;
- Validation Gate sintetico: 6 scenari, precisione 1, recall 1, F1 1, MAE importi 0;
- smoke HTTP: 4 documenti demo, una catena, 5 casi, readiness e audit validi;
- backup SQLite creato, verificato e ripristinato;
- OpenAPI e SBOM rigenerati e verificati;
- scansione dei sorgenti senza chiavi OpenAI, token nel browser o stili inline incompatibili con CSP.

## Prova app–worker–riavvio

La prova separata ha verificato un flusso asincrono completo con proposta, fattura e pagamento:

- tre documenti e tre job completati da un worker separato;
- ricostruzione di un unico Proof Graph;
- ruoli del grafo persistenti: proposta, ordine, consegna, fattura e pagamento;
- simulazione preventiva classificata `review`, punteggio 31: nessuna autorizzazione automatica;
- Self-Red-Team eseguito sugli scenari applicabili;
- readiness interamente positiva, incluso heartbeat del worker;
- catena audit valida prima e dopo il riavvio;
- dopo arresto e riavvio: documenti, job, grafo e file archiviati ancora presenti;
- hash SHA-256 dei file ricalcolati e uguali alle sorgenti iniziali.

L'evidenza macchina è conservata in `docs/evidence/app-worker-restart-proof-3.2.0-alpha.1.json`.

## Verifica PostgreSQL/RLS esterna già completata

Sul progetto Supabase gratuito `thistinti-staging` è stata verificata la separazione fra due tenant con un ruolo runtime privo di `SUPERUSER` e `BYPASSRLS`. Ogni tenant ha visto soltanto i propri dati; un inserimento cross-tenant è stato rifiutato con SQLSTATE `42501`. Supabase non riportava avvisi di sicurezza.

## Capacità effettivamente presenti

- Proof Graph spiegabile;
- riferimenti espliciti e relazioni temporali fra documenti;
- Sentinel Twin con documenti attesi e tempi appresi dallo storico privato;
- simulazione preventiva del rischio e dell'esposizione economica non duplicata;
- riconciliazione dei pagamenti;
- process conformance leggero;
- tripla verifica fra estrazione, aritmetica e coerenza del grafo;
- Self-Red-Team senza alterazione dei documenti;
- pattern pack anonimo e aggregato;
- governance che impedisce ai test sintetici di autorizzare automazioni;
- approvazione amministrativa legata a uno specifico run reale, alla versione corrente e ad almeno 30 scenari.

## Limiti dichiarati

La release è una preview da pilot controllato. Non certifica:

- accuratezza su documenti reali di una specifica azienda;
- integrazione con uno specifico ERP;
- secondo modello multimodale indipendente;
- apprendimento federato crittografico;
- scanner malware esterno realmente collegato;
- test di carico, stress e durata sull'infrastruttura finale;
- penetration test indipendente;
- conformità GDPR, legale, fiscale o contabile;
- autorizzazione a eseguire pagamenti o registrazioni contabili autonome.

La pubblicazione su GitHub e la relativa esecuzione del workflow PostgreSQL completo restano l'unica operazione esterna non eseguibile senza autenticazione GitHub dell'utente.
