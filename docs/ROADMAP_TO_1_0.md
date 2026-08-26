# ThisTinti — percorso da RC12 a 1.0 Stable

## Obiettivo finale

Il traguardo non è aggiungere continuamente funzioni, ma arrivare a **ThisTinti 1.0 Stable — Local-First Professional Edition**: installabile, comprensibile, verificabile, validata su documenti reali autorizzati e utilizzabile senza un servizio cloud gestito dall'autore.

La 1.0 non viene considerata raggiunta soltanto perché i gate automatici sono verdi. Deve esistere evidenza sul comportamento reale del prodotto, sulla qualità documentale, sull'esperienza di utenti non istruiti e sui principali rischi operativi.

## Priorità strutturali

### 1. Collaudo umano RC12

- installazione pulita e aggiornamento da release precedente;
- primo avvio, accesso locale e persistenza;
- caricamento demo e caricamento di documenti controllati;
- worker, attività, retry, arresto e riavvio;
- apertura delle segnalazioni e risalita alle prove originali;
- correzione supervisionata dei dati estratti e rianalisi;
- esportazioni, rapporti, backup e restore;
- disinstallazione con conservazione e cancellazione dati esplicite;
- registrazione di ogni difetto riproducibile.

Una RC13 ha senso soltanto per correggere problemi concreti emersi da questo passaggio o per consolidare parti fragili.

### 2. Consolidamento del motore documentale

Verificare con casi riproducibili FatturaPA/P7M, UBL/Peppol, JSON, CSV, XLSX/XLSM, PDF digitali, PDF OCR, ricevute di pagamento, matching molti-a-molti, catene ordine-consegna-fattura-pagamento, resi, note di credito, duplicati, sovrapagamenti, pagamenti orfani e documenti attesi mancanti.

Ogni errore importante corretto deve produrre un test di regressione permanente.

### 3. Dataset di validazione

Costruire una suite sintetica con:

- casi corretti;
- errori numerici e documentali;
- documenti incompleti o malformati;
- OCR pulito, degradato e ambiguo;
- catene complete e incomplete;
- duplicati e casi molti-a-molti;
- ground truth esplicita per ogni scenario.

### 4. Pilot reale

Gate minimo:

- almeno 30 scenari reali, autorizzati e anonimizzati quando necessario;
- ground truth definita prima dell'esecuzione;
- revisione competente distinta dall'esecuzione del software;
- misurazione di precision, recall, falsi positivi e falsi negativi;
- classificazione degli errori per parser, OCR, matching e regole;
- trasformazione dei difetti reali in regressioni automatiche.

### 5. Affidabilità e sicurezza

Prima della 1.0:

- stress e durata su dataset più grandi;
- crash/restart durante l'elaborazione;
- backup e restore provati;
- migrazioni e aggiornamenti verificati;
- audit dipendenze e SBOM;
- controllo di autenticazione, ruoli, sessioni, API key e isolamento tenant;
- revisione indipendente della sicurezza;
- chiusura dei rilievi critici e alti.

### 6. Distribuzione Windows definitiva

- installer e portable stabili;
- aggiornamento senza perdita dati;
- checksum e provenienza pubblici;
- release immutabili;
- firma Authenticode per gli artefatti destinati a utenti non tecnici.

## Priorità non strutturali

### 7. Esperienza utente

- audit schermata per schermata;
- riduzione di testi e controlli ridondanti;
- azione principale evidente;
- stati vuoti, caricamento, errore e conferma coerenti;
- onboarding comprensibile senza assistenza;
- percorso demo e percorso documenti propri ben distinti.

### 8. Progetto e piani

ThisTinti resta local-first e non viene trasformato in SaaS. La pagina commerciale deve riflettere questa scelta:

- Integration Pack e Self-Hosted in primo piano;
- pagamenti futuri e sponsor mantenuti secondari e inattivi;
- nessun account centrale, telemetria o cloud obbligatorio;
- nessuna infrastruttura commerciale complessa prima di una reale necessità.

### 9. Accessibilità

- tastiera completa e focus visibile;
- zoom e reflow fino al 200%;
- contrasto e semantica;
- collaudo manuale con tecnologie assistive;
- verifica professionale WCAG 2.2 AA prima della 1.0.

### 10. Documentazione e sito

- stato release coerente in README, ROADMAP e note;
- manuale utente e amministratore;
- installazione, aggiornamento, backup/restore e troubleshooting;
- limiti del prodotto dichiarati con chiarezza;
- sito con download, versione corrente, screenshot reali, changelog, licenza e documentazione.

## Cose deliberatamente fuori dal percorso 1.0

Non sono requisiti per completare il prodotto:

- SaaS gestito dall'autore;
- cloud proprietario;
- account centrali;
- pubblicità;
- telemetria invasiva;
- checkout o abbonamenti;
- nuove funzioni aggiunte soltanto per ampliare il catalogo.

## Sequenza delle versioni

### RC12

Primo collaudo umano end-to-end e raccolta sistematica dei problemi.

### RC13

Correzioni emerse dal collaudo RC12, consolidamento UX e architetturale. Nessuna espansione importante senza evidenza d'uso.

### RC14

Suite di validazione più forte e regressioni derivate dai casi documentali controllati.

### Beta 1

Pilot reale, metriche quantitative e sessioni con utenti non istruiti.

### Beta 2

Sicurezza indipendente, accessibilità, stress test, firma installer e documentazione finale.

### 1.0 Stable

La 1.0 richiede contemporaneamente:

- nessun difetto noto con rischio concreto di perdita dati;
- nessun difetto noto che possa produrre risultati economicamente fuorvianti senza evidenza o avviso;
- pilot completato e metriche documentate;
- installer firmato;
- backup/restore verificato;
- release riproducibile;
- UI comprensibile a un nuovo utente;
- documentazione e sito coerenti;
- confini del prodotto chiaramente dichiarati.

## Regola dopo la 1.0

Dopo la 1.0 il ciclo diventa **uso → feedback → correzione → nuova versione**. Le nuove funzioni devono derivare da problemi osservati o richieste reali, non dalla sola possibilità tecnica di aggiungerle.
