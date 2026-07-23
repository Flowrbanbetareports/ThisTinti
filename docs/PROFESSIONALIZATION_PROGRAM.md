# Programma di professionalizzazione di ThisTinti

## Obiettivo finale

Portare ThisTinti a una beta utilizzabile in pilot aziendali controllati, con risultati misurabili, installazione riproducibile, prove di sicurezza e confini operativi chiari. “Professionale” non significa soltanto interfaccia curata: richiede correttezza documentale, protezione dei dati, manutenibilità, tracciabilità, operazioni verificabili e validazione indipendente.

## Principi decisionali

1. Nessuna perdita o esposizione di dati.
2. Nessun falso risultato economico presentato come certezza.
3. Ogni conclusione deve restare collegata alle prove.
4. Ogni automazione deve essere reversibile, misurata e supervisionata.
5. Build, aggiornamento, backup e ripristino devono essere riproducibili.
6. Usabilità ed estetica non possono nascondere i limiti del prodotto.

## Workstream interni

### 1. Prodotto e UX

- flussi completi e coerenti per caricamento, revisione, export e amministrazione;
- errori leggibili, stati di caricamento e azioni contestuali;
- accessibilità WCAG 2.2 AA come obiettivo verificabile;
- onboarding basato su attività reali, non su terminologia tecnica.

### 2. Accuratezza e pilot

- metadati obbligatori per autorizzazione, anonimizzazione e ground truth;
- almeno 30 scenari per il gate minimo e campioni più ampi per la valutazione finale;
- rapporti redatti esportabili;
- difetti convertiti in regressioni sintetiche.

### 3. Architettura e manutenibilità

- eliminazione di patch temporanee e bundle duplicati;
- separazione progressiva di API, servizi e serializzazione;
- limiti espliciti alla dimensione dei moduli e alle dipendenze circolari;
- compatibilità Python e migrazioni reversibili mantenute come gate.

### 4. Sicurezza e privacy

- baseline OWASP ASVS 5.0 per i controlli applicativi;
- processo NIST SSDF per sviluppo, rilascio e gestione vulnerabilità;
- threat model aggiornato a ogni nuova superficie;
- file non fidati sempre in quarantena, con limiti, scanner e parser isolabili;
- review indipendente prima di dati sensibili.

### 5. Supply chain e rilascio

- dipendenze bloccate, SBOM, checksum e provenienza verificabile;
- permessi GitHub Actions ridotti per job;
- attestazioni degli artefatti ufficiali;
- firma Authenticode prima della distribuzione a utenti non tecnici.

### 6. Operazioni

- log strutturati e request ID;
- readiness fail-closed;
- SLO, test di carico e durata;
- backup off-site, restore provato e incident response esercitata;
- responsabilità del self-hosted documentate.

## Gate che non possono essere autocertificati

Il codice e la CI non possono sostituire:

- documenti reali autorizzati e revisori competenti;
- penetration test indipendente;
- verifica professionale di privacy, condizioni e marchio;
- certificato di firma del publisher;
- test sull'infrastruttura definitiva dell'organizzazione;
- decisione del titolare sui rischi residui.

## Definizione di beta

La beta è raggiunta quando:

- l'Alpha.6 supera il pilot documentale con rapporto revisionato;
- non esistono vulnerabilità critiche o alte non accettate formalmente;
- installer, checksum, SBOM e provenienza sono verificabili;
- backup e restore sono provati sull'ambiente di pilot;
- l'interfaccia supera il collaudo di accessibilità e i principali flussi end-to-end;
- i limiti e le responsabilità sono stati verificati da professionisti indipendenti.
