# Roadmap di ThisTinti

## Stato attuale — 3.4.0-alpha.6-rc.1

Completati:

- Local Edition Windows installabile, aggiornabile e disinstallabile senza rimuovere i dati;
- archivio portable, pagina pubblica, checksum e sorgente self-hosted;
- caricamento demo, esportazione, persistenza e smoke test dopo riavvio;
- PostgreSQL con ruoli separati, RLS e prove cross-tenant;
- Self-Hosted Reference Edition con Docker, TLS, scanner e procedure operative;
- CI, audit dipendenze, backup e ripristino automatici;
- identità visiva unificata, motion accessibile e collaudo Windows;
- messaggi di errore leggibili, orari locali e azioni contestuali;
- documentazione legale e operativa di base;
- gate interno beta, audit accessibilità strutturale, load probe e provenienza degli artefatti.

## Alpha.6 — pilot documentale e qualità misurata

Obiettivi interni:

- consolidare il frontend e rimuovere patch o bundle temporanei;
- rendere obbligatori autorizzazione, anonimizzazione, perimetro e doppia revisione per dataset reali;
- esportare rapporti di validazione redatti e riproducibili;
- validare dataset pilot da CLI prima del caricamento;
- migliorare accessibilità, onboarding e flussi end-to-end;
- ridurre progressivamente i moduli monolitici senza modificare il comportamento verificato;
- aggiungere provenienza verificabile agli artefatti ufficiali.

Obiettivi del pilot:

- almeno 30 scenari reali, anonimizzati e autorizzati per il gate minimo;
- campione esteso secondo `docs/VALIDATION_PROTOCOL.md` per la valutazione operativa;
- misurazione di precisione, recall, falsi positivi, falsi negativi e importo economico coinvolto;
- classificazione degli errori per parser, matching e regole;
- miglioramento dei formati e delle regole con test di regressione;
- nessuna automazione economica senza approvazione del run di validazione.

## Beta — preparazione operativa

Gate richiesti:

- penetration test indipendente;
- revisione legale, privacy e del nome;
- firma digitale degli installer;
- test di accessibilità WCAG 2.2;
- test di carico e durata con SLO definiti;
- piano di aggiornamento e risposta agli incidenti;
- policy di retention e cancellazione applicata all'ambiente definitivo;
- pilot su infrastruttura reale con backup e restore provati;
- rapporto pilot revisionato e rischi residui accettati formalmente.

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
5. manutenibilità e osservabilità;
6. usabilità e accessibilità;
7. estetica e funzioni non essenziali.
