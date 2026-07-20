# ThisTinti 3.2.0-alpha.1 — verifica locale della preview intelligence

## Esito

La preview Proof Graph & Sentinel ha superato i gate locali disponibili sul checkout corrente.

- 121 test superati;
- copertura applicativa: 91%, soglia bloccante 90%;
- Ruff, format, Bandit, compileall e sintassi JavaScript puliti;
- migrazione Alembic fino a `d42a0f61be90`, `alembic check`, downgrade completo e nuovo upgrade riusciti;
- Validation Gate sintetico: 6 scenari, precisione/recall/F1 pari a 1, MAE pari a 0;
- smoke HTTP: 4 documenti, una catena, 5 casi, readiness e audit validi;
- prova separata app/worker: proposta, fattura e pagamento elaborati asincronamente, Proof Graph creato, simulazione eseguita, self-red-team applicabile superato, riavvio e persistenza verificati;
- controlli database sulla governance: un dataset sintetico non può essere idoneo all'automazione e un run non può essere approvato senza autore, data e motivazione.

## Capacità verificate nella 3.2

- ruoli documento `proposal` e `payment`;
- collegamenti espliciti nel Proof Graph;
- documenti attesi e tempi appresi dallo storico privato;
- distinzione prudente tra beni fisici e servizi;
- simulazione preventiva con blocco delle azioni prive del documento oggetto;
- stima economica non duplicata;
- pagamenti orfani, sovrapagamenti e duplicati soltanto con riferimento comune;
- process conformance;
- self-red-team con distinzione tra scenari applicabili e non applicabili;
- pattern pack aggregato senza documenti, nomi, date, importi o identificativi;
- separazione fra regressione sintetica e pilot reale;
- approvazione amministrativa legata al run esatto e revocata da una nuova esecuzione.

## Evidenze esterne già disponibili

Sul progetto Supabase gratuito dedicato è stata verificata la separazione di due tenant mediante un ruolo runtime senza `SUPERUSER`/`BYPASSRLS`; un inserimento cross-tenant è stato rifiutato con SQLSTATE `42501`.

La prova completa su GitHub Actions resta subordinata alla pubblicazione manuale del repository privato. Il workflow è già predisposto con PostgreSQL 16, ruoli owner/runtime separati, app, worker, riavvio e artifact delle evidenze.

## Limiti non certificati

Questa verifica non sostituisce:

- pilot su documenti aziendali reali anonimizzati;
- secondo modello multimodale indipendente;
- apprendimento federato crittografico;
- scanner malware esterno effettivamente collegato;
- test di carico, stress e durata;
- penetration test indipendente;
- revisione privacy, legale e contabile;
- collaudo di uno specifico ERP.

La 3.2.0-alpha.1 è quindi una preview avanzata da pilot controllato, non una release autorizzata a eseguire azioni economiche autonome.
