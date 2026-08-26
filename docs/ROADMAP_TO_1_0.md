# ThisTinti — percorso da RC13 Public Preview a 1.0 Stable

## Obiettivo finale

Il traguardo non è aggiungere continuamente funzioni, ma arrivare a **ThisTinti 1.0 Stable — Local-First Professional Edition**: installabile, comprensibile, verificabile, validata su documenti reali autorizzati e utilizzabile senza un servizio cloud gestito dall'autore.

La 1.0 non viene considerata raggiunta soltanto perché i gate automatici sono verdi. Deve esistere evidenza sul comportamento reale del prodotto, sulla qualità documentale, sull'esperienza di utenti non istruiti e sui principali rischi operativi.

La baseline pubblica corrente è `3.4.0-alpha.7-rc.13`. RC13 è un hotfix di sicurezza pubblicato dopo due advisory `pypdf` emerse successivamente alla RC12; non rappresenta un’espansione funzionale e non sostituisce il collaudo umano previsto.

## 1. Collaudo umano della RC13

- installazione pulita e aggiornamento da release precedente;
- primo avvio, accesso locale e persistenza;
- caricamento demo e caricamento di documenti controllati;
- worker, attività, retry, arresto e riavvio;
- apertura delle segnalazioni e risalita alle prove originali;
- correzione supervisionata dei dati estratti e rianalisi;
- esportazioni, rapporti, backup e restore;
- disinstallazione con conservazione e cancellazione dati esplicite;
- zoom/reflow, tastiera e tecnologie assistive;
- registrazione di ogni difetto riproducibile.

Una nuova RC ha senso soltanto per correggere problemi concreti emersi da questi passaggi, per mitigare rischi di sicurezza/manutenzione o per consolidare parti fragili. Il numero della versione successiva non viene deciso in anticipo.

## 2. Consolidamento del motore documentale

Verificare con casi riproducibili FatturaPA/P7M, UBL/Peppol, JSON, CSV, XLSX/XLSM, PDF digitali, PDF OCR, ricevute di pagamento, matching molti-a-molti, catene ordine-consegna-fattura-pagamento, resi, note di credito, duplicati, sovrapagamenti, pagamenti orfani e documenti attesi mancanti.

Ogni errore importante corretto deve produrre un test di regressione permanente.

## 3. Suite di validazione controllata

Mantenere e ampliare una suite sintetica con:

- casi corretti;
- errori numerici e documentali;
- documenti incompleti o malformati;
- OCR pulito, degradato e ambiguo;
- catene complete e incomplete;
- duplicati e casi molti-a-molti;
- ground truth esplicita per ogni scenario.

Questa suite serve alla regressione tecnica e non sostituisce il pilot reale.

## 4. Pilot reale

Gate minimo:

- almeno 30 scenari reali, autorizzati e anonimizzati quando necessario;
- ground truth definita prima dell'esecuzione;
- revisione competente distinta dall'esecuzione del software;
- misurazione di precision, recall, falsi positivi e falsi negativi;
- classificazione degli errori per parser, OCR, matching e regole;
- trasformazione dei difetti reali in regressioni automatiche;
- rapporto redatto con versione, data, composizione del dataset, metriche e limiti.

## 5. Affidabilità e sicurezza

Prima della 1.0:

- stress e durata su dataset più grandi;
- crash/restart durante l'elaborazione;
- backup e restore provati sull'ambiente definitivo;
- migrazioni, aggiornamenti e rollback verificati;
- audit dipendenze e SBOM;
- controllo di autenticazione, ruoli, sessioni, API key e isolamento tenant;
- penetration test e revisione indipendente della sicurezza;
- chiusura e retest dei rilievi critici e alti;
- piano di risposta agli incidenti esercitato.

## 6. Distribuzione Windows definitiva

- installer e portable stabili;
- aggiornamento senza perdita dati;
- checksum e provenienza pubblici;
- release riproducibili e non sostituite silenziosamente;
- firma Authenticode e timestamp per gli artefatti destinati a utenti non tecnici;
- verifica della firma su Windows pulito.

## 7. Esperienza utente

- audit schermata per schermata;
- riduzione di testi e controlli ridondanti;
- azione principale evidente;
- stati vuoti, caricamento, errore e conferma coerenti;
- onboarding comprensibile senza assistenza;
- percorso demo e percorso documenti propri ben distinti;
- sessioni con almeno 5–10 utenti non istruiti prima della beta validata.

## 8. Progetto e piani

ThisTinti resta local-first e non viene trasformato in SaaS come requisito della 1.0. La pagina commerciale deve riflettere questa scelta:

- Integration Pack e Self-Hosted in primo piano;
- pagamenti futuri e sponsor mantenuti secondari e inattivi finché non esiste un perimetro legale/fiscale reale;
- nessun account centrale, telemetria o cloud obbligatorio;
- nessuna infrastruttura commerciale complessa prima di una reale necessità.

## 9. Accessibilità

- tastiera completa e focus visibile;
- zoom e reflow fino al 200%;
- contrasto e semantica;
- collaudo manuale con tecnologie assistive;
- verifica professionale WCAG 2.2 AA prima della 1.0.

I controlli automatici e Chromium sono regressioni utili, ma non vengono presentati come certificazione WCAG.

## 10. Legale, privacy, nome e responsabilità

Prima della 1.0 destinata a uso professionale:

- revisione professionale delle condizioni, disclaimer, privacy e licenze;
- verifica del nome/marchio nei territori e classi rilevanti;
- ruoli privacy, retention, cancellazione, incidenti e DPA definiti per il modello operativo scelto;
- revisione delle affermazioni pubbliche sul sito e nelle release;
- accettazione formale dei rischi residui da parte dell'organizzazione che mette il sistema in esercizio.

## 11. Documentazione e sito

- stato release coerente in README, ROADMAP, note e checklist;
- manuale utente e amministratore;
- installazione, aggiornamento, backup/restore e troubleshooting;
- limiti del prodotto dichiarati con chiarezza;
- sito con download della Public Preview corrente, checksum, versione, guida, changelog, licenza e documentazione;
- nessuna metrica di utenti/installazioni dedotta impropriamente dai download GitHub.

## Cose deliberatamente fuori dal percorso 1.0

Non sono requisiti per completare il prodotto:

- SaaS gestito dall'autore;
- cloud proprietario;
- account centrali;
- pubblicità;
- telemetria invasiva;
- checkout o abbonamenti;
- nuove funzioni aggiunte soltanto per ampliare il catalogo.

## Sequenza per evidenze, non per numeri di versione

### Public Preview corrente — RC13

Hotfix sicurezza PDF pubblicato e tecnicamente verificato. È la baseline su cui eseguire il collaudo umano.

### Prossima candidata, solo se necessaria

Correzioni derivate da difetti riproducibili, rilievi di sicurezza, accessibilità o validazione. Nessuna espansione importante senza evidenza d'uso.

### Beta tecnica

Gate interni completi sul commit esatto e prodotto idoneo a pilot supervisionati, senza dichiarare ancora validazione esterna.

### Beta validata

Pilot reale con metriche, sessioni con utenti non istruiti, sicurezza indipendente, accessibilità manuale/professionale, revisione legale/privacy e distribuzione firmata.

### 1.0 Stable

La 1.0 richiede contemporaneamente:

- nessun difetto noto con rischio concreto di perdita o esposizione dati non mitigato;
- nessun difetto noto che possa produrre risultati economicamente fuorvianti senza evidenza o avviso;
- pilot completato e metriche documentate;
- rilievi critici/alti di sicurezza chiusi e retestati;
- installer firmato e verificato;
- backup/restore, aggiornamento e rollback verificati nell’ambiente definitivo;
- UI comprensibile a un nuovo utente;
- accessibilità verificata manualmente con tecnologie assistive;
- documentazione e sito coerenti;
- confini del prodotto chiaramente dichiarati;
- rischi residui formalmente accettati dall’organizzazione responsabile.

## Regola dopo la 1.0

Dopo la 1.0 il ciclo diventa **uso → feedback → correzione → nuova versione**. Le nuove funzioni devono derivare da problemi osservati o richieste reali, non dalla sola possibilità tecnica di aggiungerle.
