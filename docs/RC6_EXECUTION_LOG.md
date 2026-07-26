# RC6 execution log

Questo registro distingue le prove automatiche associate alla release dai collaudi
esterni ancora necessari. Non sostituisce release note, revisione professionale o prova
manuale su hardware dell'utilizzatore.

## Public Preview pubblicata

| Voce | Evidenza verificata |
| --- | --- |
| Versione | `3.4.0-alpha.7-rc.6` |
| Tag | `v3.4.0-alpha.7-rc.6` |
| Commit sorgente | `0c86e669bbbecadcada3581dfd842a2f7fd9c3b5` |
| Tree Git | `5b42ee40bb948d6133afc50605534dd1028f478e` |
| Workflow Windows | run `30193231940`, numero `200`, conclusione `success` |
| Portable SHA-256 | `81562015e8f351f9e99ab38ee16a4f42d1af96b0d249cf436b9f9c283ad25f80` |
| Installer SHA-256 | `f77b59b3b4ef8510fc0e9773f5840962fb23e9d3353dec8730d4c595f6d6bf89` |
| Pubblicazione | prerelease immutabile, 26 luglio 2026 |

Il workflow Windows ha registrato come riusciti: gate sorgente completo, build frozen,
smoke dell'installato, aggiornamento dalla RC5, riavvio, persistenza e disinstallazione
con conservazione dei dati. La pubblicazione ha verificato commit, tree, checksum,
report di smoke e attestazioni prima di creare la prerelease.

## Problemi interni chiusi in RC6

- parsing numerico fail-closed e diagnostica strutturata;
- esempi JSON coperti da test e input non validi restituiti come errori leggibili;
- `make verify` bloccante per CI, build Windows e pubblicazione;
- OpenAPI, SBOM, versione e provenienza allineati al candidato;
- apertura dell'originale e della riga collegata a un'evidenza;
- priorità `critical`;
- centro Attività, retry e rielaborazione guidata;
- collegamento e scollegamento manuale con rianalisi.

## Limiti da non trasformare in claim

- l'installer non è firmato Authenticode;
- nessun test eseguito in CI sostituisce il collaudo manuale di Lorenzo sul proprio PC;
- non risultano pentest indipendente, collaudo WCAG manuale o pilot con corpus aziendale
  reale autorizzato;
- `local-source-smoke.json` prova l'avvio dal sorgente e contiene `frozen: false`: non è
  l'evidenza dell'eseguibile Windows distribuito;
- la copia di `windows-latest.json` inclusa nel sorgente frozen è necessariamente
  precedente al build finale; l'evidenza autorevole della release è nei record
  `builds/release-latest.json`, `builds/publication-latest.json` e negli asset pubblicati.

## Hardening successivo

La RC6 rende raggiungibile l'evidenza, ma non dimostra ancora da sola tutti gli stati
reali di errore e accessibilità. Il lavoro successivo deve coprire con test integrati:
file originale mancante o non autorizzato, documento archiviato, errori persistenti,
tastiera, reflow e zoom elevato.
