# Roadmap di ThisTinti

## Stato attuale — 3.4.0-alpha.7-rc.15 RC15 Pilot-Ready — Public Preview

La Public Preview corrente è `3.4.0-alpha.7-rc.15`. RC15 completa il workflow supervisionato di pratica, il lifecycle auditabile delle segnalazioni, il pilot workspace integrato, il profilo azienda versionato e le operazioni esplicite di export, archivio e cancellazione, mantenendo gli hardening documentali e di distribuzione consolidati nelle release precedenti.

La RC15 è stata costruita e verificata sul commit applicativo `0c99155d17374ce195db4ec65200a8edcf1bcdd1`, tree `8e91471fbaa833c10011e1863cd0049740c64225`, Windows run `33125242692` / build `513`. L’installer pubblicato ha SHA-256 `48429173e92ff189d1d968609749695a8ac9354519710850e61fd954c7d9c832`.

La RC14 resta la prerelease storica che ha consolidato benchmark, PDF/OCR, backup/restore e aggiornamento Windows; RC15 la sostituisce come versione da usare per i collaudi successivi. La pubblicazione di RC15 non rimuove i gate esterni: resta una Public Preview supervisionata, non una beta validata o una release di produzione.

Il percorso verso la 1.0 è definito in `docs/ROADMAP_TO_1_0.md`. Una nuova versione non viene creata per inerzia: deve essere giustificata da difetti riproducibili, rischi per dati o risultati, rilievi UX/accessibilità, evidenze del pilot o necessità di manutenzione/sicurezza.

## Priorità immediata — collaudo umano RC15

La priorità dopo la pubblicazione è il collaudo end-to-end della RC15 installata:

- installazione e primo avvio su Windows reale;
- percorso demo, worker, attività, retry, riavvio e persistenza;
- segnalazioni, prove originali, correzioni supervisionate e rianalisi;
- diagnostica e verbale JSON;
- backup/restore e comportamento di disinstallazione;
- zoom 125/150/200%, tastiera e tecnologie assistive;
- sessioni con utenti non istruiti e raccolta dei difetti riproducibili.

I risultati umani non vengono autocertificati dai test automatici.

## Pilot documentale e qualità misurata

Obiettivi interni:

- consolidare il frontend e rimuovere patch o bundle temporanei;
- rendere obbligatori autorizzazione, anonimizzazione, perimetro e doppia revisione per dataset reali;
- esportare rapporti di validazione redatti e riproducibili;
- validare dataset pilot da CLI prima del caricamento;
- migliorare accessibilità, onboarding e flussi end-to-end;
- ridurre progressivamente i moduli monolitici senza modificare il comportamento verificato;
- mantenere provenienza verificabile degli artefatti ufficiali.

Obiettivi del pilot:

- almeno 30 scenari reali, anonimizzati e autorizzati per il gate minimo;
- ground truth definita prima dell’esecuzione;
- misurazione di precisione, recall, falsi positivi, falsi negativi e importo economico coinvolto;
- classificazione degli errori per parser, OCR, matching e regole;
- trasformazione dei difetti confermati in test di regressione;
- nessuna automazione economica senza approvazione esplicita del run di validazione.

## Beta — preparazione operativa

Gate richiesti:

- penetration test indipendente e retest dei rilievi critici/alti;
- revisione professionale legale, privacy e del nome/marchio;
- firma Authenticode degli installer destinati a utenti non tecnici;
- collaudo WCAG 2.2 AA manuale con tecnologie assistive;
- test di carico e durata con SLO definiti;
- piano di aggiornamento, rollback e risposta agli incidenti;
- policy di retention e cancellazione applicata all'ambiente definitivo;
- pilot su infrastruttura reale con backup e restore provati;
- rapporto pilot revisionato e rischi residui accettati formalmente.

## Produzione / 1.0 Stable

La 1.0 non coincide con “tutti i test automatici verdi”. Richiede contemporaneamente evidenza tecnica, umana e indipendente: qualità documentale misurata, sicurezza revisionata, accessibilità verificata, distribuzione firmata, backup/restore e aggiornamenti provati, documentazione coerente e assenza di difetti noti ad alto rischio.

## Direzione commerciale

Nel periodo alpha ThisTinti resta:

- open source;
- gratuito;
- local-first;
- adatto a demo e pilot supervisionati;
- non offerto come SaaS o servizio gestito.

Una futura monetizzazione potrà riguardare personalizzazioni, integrazioni, distribuzioni gestite o assistenza professionale, ma soltanto con contratti e responsabilità separati dal software gratuito.

## Criterio di priorità

Le modifiche vengono ordinate secondo:

1. rischio di perdita o esposizione dei dati;
2. correttezza dei risultati documentali;
3. tracciabilità e verifica umana;
4. affidabilità dell'installazione e degli aggiornamenti;
5. sicurezza e dipendenze;
6. manutenibilità e osservabilità;
7. usabilità e accessibilità;
8. estetica e funzioni non essenziali.
