# Checklist di pubblicazione

## Base tecnica completata

- [x] Local Free Edition installabile, aggiornabile e disinstallabile senza eliminare i dati;
- [x] Self-Hosted Reference Edition con PostgreSQL, ruoli separati, RLS, scanner e procedure operative;
- [x] licenza, condizioni, disclaimer, privacy, marchio e politica di supporto;
- [x] pagina statica senza analytics o telemetria;
- [x] checksum, SBOM, provenienza degli artefatti e workflow di release;
- [x] guide utente, backup, ripristino, aggiornamento e disinstallazione;
- [x] kit pilot, validatore dataset, brief legale e pacchetto security review;
- [x] gate automatici di pubblicazione e preparazione alla beta;
- [x] audit dipendenze, migrazioni reversibili e compatibilità Python;
- [x] ciclo Windows verificato: build, installazione precedente, aggiornamento, persistenza, smoke test e disinstallazione;
- [x] prova self-hosted: avvio, amministratore, accettazione autenticata, backup, riavvio e persistenza;
- [x] controllo strutturale di accessibilità e load probe di regressione;
- [x] evidenza interna del candidato registrata in `docs/evidence/beta/internal-candidate-summary.json`.

## Stato della candidata tecnica

- [x] versione `3.4.0-alpha.6-rc.1` coerente in applicazione, pacchetti e documentazione;
- [x] repository e codice reale integrati in `main`;
- [x] build Windows prodotta dal commit esatto del candidato;
- [x] artefatti e checksum verificati;
- [x] nessuna vulnerabilità nota bloccante rilevata dai controlli automatici;
- [x] limiti e gate esterni dichiarati senza presentare la candidata come beta validata.

## Gate esterni prima della beta validata

- [ ] almeno 30 scenari documentali reali, autorizzati e anonimizzati;
- [ ] ground truth definita prima dell'esecuzione da revisori competenti;
- [ ] rapporto pilot revisionato con precisione, richiamo, falsi positivi e falsi negativi;
- [ ] penetration test indipendente e retest dei rilievi;
- [ ] revisione professionale di privacy, condizioni d'uso e nome/marchio;
- [ ] collaudo WCAG 2.2 AA manuale con tastiera e tecnologie assistive;
- [ ] test di carico, durata, backup e ripristino sull'infrastruttura definitiva;
- [ ] certificato Authenticode, timestamp e verifica della firma su Windows pulito;
- [ ] accettazione formale dei rischi residui da parte dell'organizzazione responsabile.

## Gate prima della produzione

- [ ] SLO, RPO, RTO, capacità e retention approvati;
- [ ] procedura incidenti esercitata;
- [ ] monitoraggio, log e responsabilità operative definiti;
- [ ] piano di aggiornamento e rollback provato nell'ambiente definitivo;
- [ ] decisione formale di messa in esercizio.

## Regola di rilascio

Finché i gate esterni non sono documentati, ThisTinti resta una candidata tecnica destinata a demo e pilot supervisionati. Non deve essere descritto come certificato, infallibile, pronto per qualsiasi azienda o idoneo ad autorizzare decisioni economiche autonome.
