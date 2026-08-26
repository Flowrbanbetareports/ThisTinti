# Roadmap di ThisTinti

## Stato attuale — 3.4.0-alpha.7-rc.13 Public Preview

La Public Preview corrente è `3.4.0-alpha.7-rc.13`, pubblicata come prerelease dopo la correzione di sicurezza `pypdf` 6.14.2 → 6.15.0 per `PYSEC-2026-3655` e `PYSEC-2026-3656`.

La RC13 è stata costruita e verificata sul commit applicativo `f7609b51aec4c358d0410ca8ff83e60485cac96c`, tree `e1a5ea29d4bbef7e1431d96fa5a5149dc4a46e3c`, Windows run `33008478384` / build `394`. L’installer pubblicato ha SHA-256 `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`.

RC13 non aggiunge funzionalità o modifiche UI rispetto alla RC12: è stata anticipata rispetto al collaudo umano complessivo perché il dependency audit ha rilevato due advisory che ricadevano direttamente nel perimetro reale del parser PDF. La RC12 resta una release storica immutabile; RC13 è la versione da usare per i collaudi successivi.

Il percorso verso la 1.0 è definito in `docs/ROADMAP_TO_1_0.md`. Una nuova versione non viene creata per inerzia: deve essere giustificata da difetti riproducibili, rischi per dati o risultati, rilievi UX/accessibilità, evidenze del pilot o necessità di manutenzione/sicurezza.

## Priorità immediata — collaudo umano RC13

La priorità dopo la pubblicazione è il collaudo end-to-end della RC13 installata:

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
