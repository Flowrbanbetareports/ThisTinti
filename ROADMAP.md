# Roadmap di ThisTinti

## Stato attuale — 3.4.0-alpha.7-rc.13 candidata interna di sicurezza; 3.4.0-alpha.7-rc.12 Public Preview

La candidata interna corrente è `3.4.0-alpha.7-rc.13` e contiene esclusivamente la correzione pypdf 6.15.0 per due advisory emerse dal dependency audit. La Public Preview pubblica corrente resta `3.4.0-alpha.7-rc.12`, distribuita come release immutabile con checksum, provenienza e attestazioni. RC12 mantiene il prodotto gratuito e local-first e aggiunge soltanto una pagina amministratore per metriche pubbliche, un Integration Pack in anteprima e predisposizioni disattivate per piani, sponsor e acquisto digitale.

Il lavoro successivo non parte automaticamente da una RC13: prima viene completato il collaudo umano end-to-end della RC12 installata. Una nuova candidata è giustificata soltanto da difetti riproducibili, rischi per i dati o i risultati documentali, blocchi UX/accessibilità rilevanti o consolidamenti necessari a correggerli. Il percorso verso la 1.0 è definito in `docs/ROADMAP_TO_1_0.md`.

## RC8 — collaudo direttamente nell’app

La diagnostica permette a Lorenzo di svolgere il collaudo dalla UI e distingue
`PASS`, `PARZIALE`, `FAIL` e `NON ESEGUITO`. I gate automatici e l’artefatto
Windows del commit candidato sono registrati in `docs/RC8_EXECUTION_LOG.md`.
Prima della pubblicazione restano l’accettazione in-app e le prove manuali di
zoom, tastiera e tecnologia assistiva descritte in
`docs/RC8_IN_APP_ACCEPTANCE_LORENZO.md`.

## Pilot documentale e qualità misurata

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
