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

## Pilot Procurement e qualità misurata

La baseline metodologica operativa è `docs/PROCUREMENT_PILOT_PROTOCOL.md`, supportata da `scripts/procurement_pilot_protocol.py`.

Il pilot separa sviluppo e valutazione:

- 5–10 pratiche di calibrazione, con modifiche consentite;
- freeze di software, Practice Model, Rule Pack, profilo azienda, protocolli e case register;
- Pilot Manifest sigillato con versioni, commit e hash;
- ground truth blind creata prima dell'analisi di ThisTinti;
- 20–25 pratiche blind mai usate per calibrare, senza modifiche durante il run;
- rapporto con conteggi grezzi, intervalli d'incertezza, risultati per tipologia, critical miss e metriche economiche;
- backlog degli errori destinato esclusivamente alla versione successiva.

La separazione tra calibrazione e blind set deve evitare leakage da famiglie documentali, template, fornitori o altri gruppi fortemente simili. Se cambia un artefatto congelato, quel run termina e viene creato un nuovo Manifest; risultati di versioni differenti non vengono presentati come un unico esperimento.

La ground truth preferita usa due revisori indipendenti seguiti da adjudication. Se è disponibile un solo revisore qualificato, il limite metodologico viene dichiarato esplicitamente e non viene simulata una doppia revisione.

Gli hash dei singoli documenti aziendali restano nell'inventario privato locale. I rapporti pubblici non espongono impronte di file riservati senza autorizzazione.

Practice Model e Rule Pack Procurement restano provvisori (`v0.x`) fino all'evidenza raccolta sui casi reali. Non viene dichiarato un modello universale della pratica prima che più dataset e organizzazioni dimostrino una generalizzazione reale.

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
