# Condizioni d’uso e avviso sui rischi — ThisTinti Free Editions

**Versione dell’avviso:** 2026-07-20-v2
**Ultimo aggiornamento:** 20 luglio 2026

## 1. Documenti applicabili e prevalenza

Il codice sorgente di ThisTinti è concesso secondo la **Apache License, Version 2.0**, contenuta nel file `LICENSE`. La licenza disciplina i diritti di utilizzo, copia, modifica e redistribuzione del software.

Le presenti condizioni descrivono lo scopo, i rischi e le responsabilità operative delle distribuzioni ufficiali Local Free Edition e Self-Hosted Reference Edition. Non riducono i diritti riconosciuti dalla Apache License 2.0. In caso di contrasto prevalgono la licenza open source e le norme inderogabili applicabili.

## 2. Natura del progetto e assenza di servizio gestito

ThisTinti è software libero e gratuito distribuito senza account centrale dell’autore, telemetria applicativa, cloud obbligatorio, assistenza garantita o accordo sul livello di servizio. L’autore non installa, configura, amministra, monitora o gestisce le installazioni degli utilizzatori e non riceve i documenti elaborati nelle configurazioni ufficiali locali o self-hosted.

La Self-Hosted Reference Edition è esclusivamente una configurazione tecnica di riferimento. Non costituisce hosting, outsourcing, amministrazione di sistema, consulenza, certificazione, collaudo dell’infrastruttura dell’utilizzatore o assunzione di responsabilità operativa.

Il download, la documentazione, le release e gli eventuali aggiornamenti non costituiscono promessa di continuità, manutenzione, compatibilità futura, correzione degli errori o assistenza.

## 3. Scopo previsto e usi non coperti

ThisTinti è uno strumento di supporto al controllo documentale aziendale. Può estrarre dati, collegare documenti, segnalare possibili anomalie e formulare valutazioni probabilistiche o basate su regole.

Non è progettato, certificato o garantito come:

- sistema contabile, fiscale, legale o di revisione;
- sistema di autorizzazione, esecuzione o blocco dei pagamenti;
- sistema antifrode o di conformità normativa completo;
- sistema destinato a decisioni mediche, occupazionali, creditizie, assicurative, giudiziarie, di sicurezza pubblica o comunque ad alto rischio;
- componente di sicurezza, emergenza o infrastruttura critica;
- sostituto dei documenti originali, dei professionisti abilitati o dei controlli interni dell’organizzazione.

Qualsiasi impiego diverso dallo scopo descritto avviene sotto l’esclusiva valutazione e responsabilità dell’utilizzatore, dell’operatore dell’infrastruttura e dell’eventuale integratore.

## 4. Verifica umana obbligatoria

Gli output possono essere incompleti, errati, ambigui o non aggiornati. OCR, parser, regole, modelli statistici e funzioni di intelligence possono generare falsi positivi e falsi negativi.

L’utilizzatore deve sempre:

1. consultare i documenti originali;
2. verificare quantità, importi, date, soggetti, riferimenti e conclusioni;
3. sottoporre le decisioni economiche, contabili, fiscali, legali e regolamentari a una persona competente;
4. impedire che ThisTinti sia l’unica base di un pagamento, una registrazione contabile, una dichiarazione, una contestazione o una decisione verso terzi.

Le indicazioni “basso rischio”, “coerente”, “pagamento riconciliato”, “automazione consentita” o equivalenti non costituiscono garanzia né autorizzazione giuridica o finanziaria.

## 5. Responsabilità dell’utilizzatore e dell’operatore self-hosted

L’utilizzatore e, per la Self-Hosted Reference Edition, l’organizzazione o il fornitore che gestisce l’infrastruttura sono responsabili di:

- liceità, correttezza e disponibilità dei documenti caricati;
- base giuridica, informative, autorizzazioni, tempi di conservazione e diritti degli interessati;
- scelta, configurazione, protezione e disponibilità di server, reti, DNS, TLS, database, storage, scanner malware, proxy, container e servizi cloud;
- credenziali, ruoli, accessi, registri, segmentazione di rete, hardening e gestione delle vulnerabilità;
- installazione, aggiornamento e verifica di sistema operativo, Docker, immagini, dipendenze e componenti di terze parti;
- backup regolari, conservazione separata, cifratura quando necessaria, verifica dei backup e prove periodiche di ripristino;
- monitoraggio, capacità, costi, continuità operativa, disaster recovery e risposta agli incidenti;
- test di carico, penetration test, revisione privacy e sicurezza prima dell’uso produttivo;
- conformità alle norme applicabili al proprio settore e territorio;
- scelta e supervisione di personale qualificato per installazione, personalizzazione, integrazione e manutenzione.

I costi e i rapporti contrattuali relativi a hosting, cloud, consulenti, integratori, certificati, domini, sicurezza e supporto sono esclusivamente tra l’organizzazione e i fornitori da essa scelti.

## 6. Dati e privacy

La Local Edition opera su `127.0.0.1`. La Self-Hosted Reference Edition conserva ed elabora i dati nell’infrastruttura scelta e amministrata dall’operatore. Nelle configurazioni ufficiali non è prevista trasmissione di documenti o telemetria applicativa all’autore.

L’autore non determina finalità e mezzi del trattamento svolto nelle installazioni autonome e non accede ai dati dell’organizzazione. L’utilizzatore, l’operatore e gli eventuali fornitori scelti dall’organizzazione devono qualificare autonomamente i rispettivi ruoli privacy e disciplinarli quando necessario.

## 7. Sicurezza, backup e continuità

Nessun software è immune da vulnerabilità, perdita di dati, incompatibilità, malware o errori. Test, checksum, audit log, container, TLS, backup o controlli automatici non equivalgono a certificazione, garanzia di sicurezza o conformità.

Prima di elaborare documenti reali, l’organizzazione deve eseguire un collaudo indipendente in un ambiente separato, predisporre backup e ripristino, mantenere una procedura manuale alternativa e stabilire criteri di sospensione del servizio. La configurazione di riferimento non deve essere esposta a Internet senza revisione professionale della specifica infrastruttura.

## 8. Assenza di garanzie

Nei limiti massimi consentiti dalla legge applicabile, software, configurazioni, file, documentazione, risultati e aggiornamenti sono forniti **“così come sono”** e **“come disponibili”**, senza garanzie espresse o implicite, incluse accuratezza, affidabilità, disponibilità, idoneità a uno scopo particolare, commerciabilità, non violazione, assenza di errori, sicurezza o compatibilità.

Una configurazione denominata “self-hosted”, “reference” o “enterprise-ready” descrive un’architettura estendibile e non una certificazione di idoneità produttiva per una specifica organizzazione.

## 9. Limitazione di responsabilità

Nei limiti massimi consentiti dalla legge applicabile, autore e contributori non rispondono di danni diretti o indiretti, perdita di dati, profitto o avviamento, interruzione dell’attività, errori di pagamento, sanzioni, contestazioni, costi infrastrutturali, compromissioni, indisponibilità, costi di ripristino o danni derivanti dall’uso, dall’impossibilità di usare o dall’affidamento sugli output o sulle configurazioni di ThisTinti.

Questa clausola non esclude né limita responsabilità che non possano essere escluse per legge, incluse quelle derivanti da dolo o colpa grave, ove applicabile. Nessuna formulazione deve essere interpretata come rinuncia a diritti inderogabili.

## 10. Modifiche, fork, integrazioni e distribuzioni di terzi

La Apache License 2.0 consente modifiche e redistribuzioni. Tuttavia:

- l’autore non controlla, approva o garantisce versioni modificate, fork, plugin, modelli, regole, installer, immagini container o servizi di terzi;
- chi modifica, integra, ridistribuisce, ospita o commercializza il software opera per proprio conto e risponde delle proprie modifiche, promesse, garanzie, assistenza e conformità;
- una versione modificata deve essere identificata chiaramente come tale e non deve suggerire approvazione, certificazione o gestione da parte dell’autore originario;
- il nome e il logo ThisTinti non sono concessi dalla Apache License 2.0 per presentare una versione modificata come distribuzione ufficiale.

## 11. Nessuna assistenza, manutenzione o obbligo di aggiornamento

Non sono garantiti supporto, correzioni, risposte, aggiornamenti di sicurezza, disponibilità del sito, conservazione delle release o compatibilità futura. L’utilizzatore e l’operatore self-hosted devono predisporre autonomamente manutenzione, monitoraggio, reperibilità e continuità operativa.

## 12. Componenti e servizi di terze parti

ThisTinti include o utilizza componenti open source e immagini di terze parti soggetti alle rispettive licenze, politiche e cicli di sicurezza. L’organizzazione deve verificarne provenienza, versioni, vulnerabilità e condizioni. L’autore non è parte dei contratti tra l’organizzazione e i fornitori di infrastruttura o assistenza.

## 13. Evidenza locale dell’accettazione self-hosted

Lo script ufficiale di inizializzazione self-hosted richiede conferme esplicite e crea un file locale con identificativo del deployment, data e hash dei documenti legali. Il file:

- resta nell’infrastruttura dell’operatore;
- non viene trasmesso all’autore;
- serve a impedire l’avvio accidentale della configurazione di riferimento senza presa visione;
- non trasferisce all’autore il controllo dell’installazione e non sostituisce contratti o valutazioni legali dell’organizzazione.

La rimozione o modifica dei controlli da parte di un fork è una scelta dell’integratore, che ne assume le conseguenze.

## 14. Norme inderogabili

Nulla nelle presenti condizioni modifica obblighi o responsabilità inderogabili previsti dalla legge applicabile. Se una clausola è invalida o inefficace, le altre rimangono applicabili nella misura consentita.

## 15. Approvazione specifica

L’installer, il primo avvio locale e l’inizializzazione self-hosted richiedono prese visione distinte. Ai sensi e per gli effetti degli articoli 1341 e 1342 del Codice civile italiano, ove applicabili, l’utilizzatore o l’operatore dichiara di approvare specificamente le clausole: **3 (scopo e usi non coperti), 4 (verifica umana), 5 (responsabilità dell’utilizzatore e operatore), 7 (sicurezza e continuità), 8 (assenza di garanzie), 9 (limitazione di responsabilità), 10 (modifiche e terzi), 11 (assenza di assistenza), 12 (componenti e servizi di terzi), 13 (evidenza locale self-hosted)**.
