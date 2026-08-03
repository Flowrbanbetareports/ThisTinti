# Stato di preparazione alla beta

## Definizioni

- **Beta tecnica candidata**: il codice, la distribuzione e le procedure interne superano i gate automatici e sono adatti a un pilot controllato.
- **Beta validata**: oltre ai gate tecnici, esistono evidenze indipendenti su accuratezza reale, sicurezza, privacy, accessibilità e operazioni.
- **Produzione**: non è implicata dalla parola beta e richiede una decisione formale dell'organizzazione che gestisce il sistema.

## Stato attuale

ThisTinti è in preparazione interna come `3.4.0-alpha.7-rc.12`. L’ultima Public Preview pubblicata e immutabile è `3.4.0-alpha.7-rc.11`. La base tecnica include:

- test applicativi e copertura minima del 90%;
- migrazioni reversibili;
- PostgreSQL con ruoli separati e RLS;
- prova self-hosted con backup, ripristino e riavvio;
- ciclo Windows di installazione, aggiornamento e disinstallazione con conservazione dei dati;
- audit delle dipendenze, SBOM, checksum e workflow con action bloccate a commit immutabili;
- governance del Validation Lab e validatore preventivo dei dataset pilota;
- controlli automatici di accessibilità strutturale e prestazioni di base;
- esperienza iniziale semplificata con anteprima senza account, guida permanente e progressive disclosure;
- navigazione laterale con overflow reale verificato in Chromium e gestione di touchpad, rotella e tastiera sull’intera colonna blu;
- percorso locale di creazione o accesso selezionato automaticamente in base allo stato del database;
- validazione numerica fail-closed e gestione leggibile degli input documentali non validi;
- evidenze apribili dal caso fino al documento originale e alla riga estratta;
- severità `critical` distinta e ordinata prima delle altre priorità;
- centro attività persistente con stato, errore, retry, cancellazione e rielaborazione guidata;
- collegamenti proposti spiegati e collegamento/scollegamento manuale con rianalisi;
- browser E2E dei flussi di recupero e collegamento contro API, database e worker reali;
- reflow equivalente al 125%, 150% e 200%, apertura delle catene da tastiera e navigazione mobile compatta;
- identità di build incorporata in ogni archivio portable e verificata insieme alla provenienza del candidato;
- protocollo di pilot senza telemetria per misurare comprensione e completamento del primo percorso.
- diagnostica locale in-app con esiti non ambigui, test numerico reale e verbale JSON scaricabile.
- estrazione OCR prudente di righe etichettate, con valori numerici fail-closed e confronto dei totali;
- gate sintetico bloccante su scansioni pulite e a basso contrasto;
- toolkit pilot locale senza comunicazioni o azioni esterne automatiche.
- centro operativo con pratiche raggruppate, priorità spiegata e storico della revisione;
- correzione supervisionata delle righe estratte con audit, provenienza e rianalisi;
- prova Chromium reale del percorso operativo e rapporto con misure non inventate;
- suggerimenti di apprendimento non automatici e vincolati a decisioni umane sufficienti.
- terminologia operativa, numeri e priorità ripuliti senza alterare i dati o le decisioni umane;
- controllo Chromium dedicato alla qualità percepita e alla gerarchia dell’interfaccia;
- gate di dimensione per impedire ulteriore crescita dei moduli principali.

## Gate interni

I gate interni sono verificati da `scripts/check_beta_readiness.py`, dal workflow `Beta Readiness` e dal workflow `Simplified Product Experience`. Devono restare verdi sul commit esatto candidato alla distribuzione. Le evidenze automatiche vengono conservate come artifact temporanei associati al run e al commit. Ogni modifica successiva invalida l'esito precedente e richiede una nuova esecuzione completa.

## Gate esterni non autocertificabili

La beta non può essere dichiarata validata senza:

1. almeno 30 scenari documentali reali, autorizzati e anonimizzati;
2. ground truth definita prima dell'esecuzione da revisori competenti;
3. rapporto pilot revisionato con precisione, richiamo, falsi positivi e falsi negativi;
4. penetration test indipendente e chiusura dei rilievi critici o alti;
5. revisione professionale di privacy, condizioni d'uso e nome/marchio;
6. collaudo WCAG 2.2 AA con tecnologie assistive e verifica manuale;
7. prova di carico, backup e ripristino sull'infrastruttura definitiva;
8. firma Authenticode degli artefatti Windows destinati a utenti non tecnici;
9. sessioni con utenti non istruiti che confermino la comprensione del primo percorso.

Lo stato di questi gate è registrato in `docs/evidence/beta/external-gates.json`. Un valore `false` è un blocco intenzionale, non un difetto del controllo.

## Regola di rilascio

Finché almeno un gate esterno resta aperto, il prodotto può essere distribuito soltanto come alpha/RC per demo o pilot supervisionati. Non deve essere descritto come certificato, infallibile, pronto per qualsiasi azienda o idoneo a decisioni economiche autonome.
