# Checklist di pubblicazione e validazione

## Public Preview corrente

Versione: `3.4.0-alpha.7-rc.13` — Public Preview.

Evidenza di pubblicazione:

- [x] sorgente di rilascio: commit `f7609b51aec4c358d0410ca8ff83e60485cac96c`;
- [x] tree Git: `e1a5ea29d4bbef7e1431d96fa5a5149dc4a46e3c`;
- [x] build Windows sul commit esatto: run `33008478384`, build `394`;
- [x] installer `ThisTinti-Setup-3.4.0-alpha.7-rc.13-x64.exe`;
- [x] SHA-256 installer `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`;
- [x] release `v3.4.0-alpha.7-rc.13` pubblicata il `2026-08-26T20:17:41Z`;
- [x] 23 asset di release confrontati con gli artefatti verificati localmente dal workflow di pubblicazione.

## Base tecnica completata per la Public Preview

- [x] Local Edition installabile, aggiornabile e disinstallabile senza eliminare implicitamente i dati;
- [x] Self-Hosted Reference Edition con PostgreSQL, ruoli separati, RLS, scanner e procedure operative;
- [x] licenza, condizioni, disclaimer, privacy, marchio e politica di supporto presenti;
- [x] sito statico senza analytics o telemetria applicativa;
- [x] checksum, SBOM, provenienza degli artefatti e workflow di release;
- [x] guide utente, backup, ripristino, aggiornamento e disinstallazione;
- [x] kit pilot, validatore dataset, brief legale e materiale per security review;
- [x] gate automatici di pubblicazione e preparazione alla beta;
- [x] dependency audit, migrazioni reversibili e compatibilità Python;
- [x] correzione `pypdf` 6.14.2 → 6.15.0 per `PYSEC-2026-3655` e `PYSEC-2026-3656`;
- [x] ciclo Windows RC13 verificato: build, baseline precedente, aggiornamento, persistenza, smoke test, Diagnostica e disinstallazione;
- [x] artefatti RC13 con checksum, identità e provenienza coerenti;
- [x] prova self-hosted automatizzata con avvio, amministratore, accettazione autenticata, backup, riavvio e persistenza;
- [x] controlli automatici di accessibilità strutturale e regressione di reflow;
- [x] pre-pilot sintetico riproducibile usato soltanto come regressione tecnica;
- [x] limiti e gate esterni dichiarati senza presentare la Public Preview come beta validata o produzione.

## Collaudo umano della Public Preview RC13

Questi punti richiedono una persona e non vengono marcati come completati sulla base dei test automatici:

- [ ] installazione e primo avvio osservati su un normale PC Windows;
- [ ] navigazione completa delle schermate principali senza assistenza tecnica;
- [ ] demo, worker, attività, retry, arresto/riavvio e persistenza verificati manualmente;
- [ ] apertura delle segnalazioni e risalita ai documenti/prove originali;
- [ ] correzione supervisionata e rianalisi verificate manualmente;
- [ ] backup/restore e comportamento di disinstallazione verificati dall’utilizzatore;
- [ ] verbale Diagnostica scaricato e controllato dall’utilizzatore;
- [ ] zoom 125%, 150% e 200% controllato manualmente;
- [ ] percorso completo da tastiera controllato da una persona;
- [ ] spot check con screen reader / tecnologia assistiva;
- [ ] 5–10 sessioni con utenti non istruiti e rilievi seri risolti.

## Gate esterni prima della beta validata

- [ ] almeno 30 scenari documentali reali, autorizzati e anonimizzati quando necessario;
- [ ] ground truth definita prima dell'esecuzione da revisori competenti;
- [ ] rapporto pilot revisionato con precisione, richiamo, falsi positivi e falsi negativi;
- [ ] penetration test indipendente e retest dei rilievi critici/alti;
- [ ] revisione professionale di privacy, condizioni d'uso, licenze e nome/marchio;
- [ ] collaudo WCAG 2.2 AA manuale/professionale con tecnologie assistive;
- [ ] test di carico, durata, backup e ripristino sull'infrastruttura definitiva;
- [ ] certificato Authenticode, timestamp e verifica della firma su Windows pulito;
- [ ] accettazione formale dei rischi residui da parte dell'organizzazione responsabile.

## Gate prima della produzione / 1.0 Stable

- [ ] SLO, RPO, RTO, capacità e retention approvati;
- [ ] procedura incidenti esercitata;
- [ ] monitoraggio, log e responsabilità operative definiti;
- [ ] piano di aggiornamento e rollback provato nell'ambiente definitivo;
- [ ] tutti i rilievi critici/alti di sicurezza chiusi e retestati;
- [ ] metriche del pilot accettate per il perimetro d’uso previsto;
- [ ] documentazione e sito verificati contro la release finale;
- [ ] decisione formale di messa in esercizio.

## Regola di rilascio

La RC13 può essere distribuita come **Public Preview alpha/RC per demo, valutazione e pilot supervisionati** perché i gate tecnici di pubblicazione sono verificati. Finché i gate umani ed esterni sopra elencati non producono evidenza reale, ThisTinti non deve essere descritto come certificato, infallibile, beta validata, pronto per qualsiasi azienda o idoneo ad autorizzare decisioni economiche autonome.
