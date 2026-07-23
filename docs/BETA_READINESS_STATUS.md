# Stato di preparazione alla beta

## Definizioni

- **Beta tecnica candidata**: il codice, la distribuzione e le procedure interne superano i gate automatici e sono adatti a un pilot controllato.
- **Beta validata**: oltre ai gate tecnici, esistono evidenze indipendenti su accuratezza reale, sicurezza, privacy, accessibilità e operazioni.
- **Produzione**: non è implicata dalla parola beta e richiede una decisione formale dell'organizzazione che gestisce il sistema.

## Stato attuale

ThisTinti è in preparazione come `3.4.0-alpha.6-rc.1`. La base tecnica include:

- test applicativi e copertura minima del 90%;
- migrazioni reversibili;
- PostgreSQL con ruoli separati e RLS;
- prova self-hosted con backup, ripristino e riavvio;
- ciclo Windows di installazione, aggiornamento e disinstallazione con conservazione dei dati;
- audit delle dipendenze, SBOM, checksum e workflow con action bloccate a commit immutabili;
- governance del Validation Lab e validatore preventivo dei dataset pilota;
- controlli automatici di accessibilità strutturale e prestazioni di base.

## Gate interni

I gate interni sono verificati da `scripts/check_beta_readiness.py` e dal workflow `Beta Readiness`. Devono restare verdi sul commit esatto candidato alla distribuzione. Le evidenze automatiche vengono conservate come artifact temporanei associati al run e al commit.

## Gate esterni non autocertificabili

La beta non può essere dichiarata validata senza:

1. almeno 30 scenari documentali reali, autorizzati e anonimizzati;
2. ground truth definita prima dell'esecuzione da revisori competenti;
3. rapporto pilot revisionato con precisione, richiamo, falsi positivi e falsi negativi;
4. penetration test indipendente e chiusura dei rilievi critici o alti;
5. revisione professionale di privacy, condizioni d'uso e nome/marchio;
6. collaudo WCAG 2.2 AA con tecnologie assistive e verifica manuale;
7. prova di carico, backup e ripristino sull'infrastruttura definitiva;
8. firma Authenticode degli artefatti Windows destinati a utenti non tecnici.

Lo stato di questi gate è registrato in `docs/evidence/beta/external-gates.json`. Un valore `false` è un blocco intenzionale, non un difetto del controllo.

## Regola di rilascio

Finché almeno un gate esterno resta aperto, il prodotto può essere distribuito soltanto come alpha/RC per demo o pilot supervisionati. Non deve essere descritto come certificato, infallibile, pronto per qualsiasi azienda o idoneo a decisioni economiche autonome.
