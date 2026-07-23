# ThisTinti — programma di semplificazione, onboarding e pubblicazione

Stato: progetto di prodotto e implementazione progressiva

Versione iniziale del programma: 2026-07-24

## 1. Decisione di prodotto

ThisTinti deve restare tecnicamente potente ma apparire semplice nel primo utilizzo.

La regola guida è:

> Un nuovo utente deve capire in meno di tre minuti che ThisTinti carica documenti collegati, li mette in ordine e mostra ciò che merita un controllo.

Le funzioni avanzate non vengono eliminate. Vengono presentate soltanto quando servono e con nomi comprensibili.

## 2. Vincoli non negoziabili

Il programma di semplificazione deve rispettare questi limiti:

1. nessun servizio cloud obbligatorio;
2. nessun account centrale ThisTinti;
3. nessuna telemetria remota;
4. nessun documento inviato all'autore;
5. nessuna API esterna necessaria per l'onboarding;
6. nessuna promessa di accuratezza, conformità o decisione automatica;
7. nessun nuovo trattamento di dati personali da parte dell'autore;
8. nessun costo operativo ricorrente;
9. nessuna duplicazione del motore o creazione di applicazioni separate;
10. compatibilità con Local Edition e Self-Hosted Reference Edition.

## 3. Problema da risolvere

L'interfaccia corrente espone contemporaneamente Panoramica, Documenti, Catene, Anomalie, Autopilota, Validation Lab, Audit e Utenti. I nomi sono corretti dal punto di vista tecnico, ma un utente nuovo può non sapere:

- da dove iniziare;
- quali pagine sono indispensabili;
- che cosa significhi una catena documentale;
- se un'anomalia sia una conclusione o soltanto una segnalazione;
- perché esistano funzioni di validazione e automazione;
- quando usare documenti reali;
- quale sia il risultato minimo di una prima prova riuscita.

Il rischio è che la ricchezza funzionale venga percepita come complessità operativa.

## 4. Obiettivi misurabili

### 4.1 Comprensione

Dopo una prova guidata, almeno 8 tester su 10 devono saper spiegare senza suggerimenti che:

- ThisTinti collega documenti riferiti alla stessa attività;
- confronta informazioni compatibili;
- mostra possibili differenze;
- non decide quale documento sia corretto;
- il risultato deve essere verificato sui documenti originali.

### 4.2 Primo risultato

Un nuovo amministratore deve poter:

1. creare lo spazio locale;
2. caricare i documenti dimostrativi;
3. aprire una segnalazione;
4. vedere le prove collegate;

in un tempo-obiettivo inferiore a tre minuti, senza manuale esterno.

### 4.3 Navigazione

Nel percorso iniziale devono essere visibili soltanto le funzioni essenziali:

- Inizio;
- Documenti;
- Da controllare;
- Guida.

Le funzioni specialistiche devono essere raccolte sotto Strumenti avanzati.

### 4.4 Sicurezza e privacy

La semplificazione non deve:

- indebolire autenticazione, ruoli, CSRF o separazione tenant;
- creare account dimostrativi condivisi;
- salvare token in localStorage o sessionStorage;
- caricare automaticamente documenti senza azione esplicita;
- usare dati personali nella demo;
- aggiungere chiamate verso servizi esterni.

## 5. Principi di progettazione

### 5.1 Progressive disclosure

Mostrare prima il percorso minimo. Rendere disponibili i dettagli tecnici senza imporli.

### 5.2 Una schermata, una domanda

Ogni vista principale deve rispondere a una domanda evidente:

- Inizio: che cosa sta succedendo?
- Documenti: che cosa ho caricato?
- Da controllare: che cosa merita attenzione?
- Collegamenti: quali documenti appartengono alla stessa attività?
- Regole proposte: quali controlli ha suggerito il sistema?

### 5.3 Linguaggio descrittivo, non autoritativo

Usare:

- possibile differenza;
- da controllare;
- documenti collegati;
- prova disponibile;
- suggerimento;
- verifica umana.

Evitare:

- errore certo;
- documento sbagliato;
- approvato automaticamente;
- conforme;
- certificato;
- frode rilevata;
- decisione corretta.

### 5.4 Dimostrare prima di spiegare

Il primo percorso deve mostrare tre documenti, un collegamento e una differenza concreta. La teoria viene dopo.

### 5.5 Reversibilità

Introduzione, guida e raggruppamento del menu devono poter essere disattivati o modificati senza toccare il motore documentale.

## 6. Architettura dell'esperienza

### 6.1 Prima dell'accesso

La schermata di accesso mantiene Accedi e Crea spazio.

Viene aggiunta una presentazione visuale non interattiva con il motore, accessibile senza account:

1. tre documenti di esempio;
2. collegamento tra i documenti;
3. una quantità discordante;
4. spiegazione del fatto che ThisTinti segnala ma non decide.

Questa anteprima non crea utenti, non scrive nel database e non simula risultati reali.

### 6.2 Primo ingresso nello spazio

Il primo ingresso mostra un'introduzione breve e chiudibile:

- Prova con esempio;
- Carica documenti;
- Apri la guida;
- Non mostrare più.

La preferenza viene conservata soltanto nel browser locale. Non contiene dati di autenticazione.

### 6.3 Stato vuoto

Quando non esistono documenti, la Panoramica deve presentare una scheda di partenza con due azioni:

- Prova con documenti dimostrativi;
- Carica documenti autorizzati.

Le metriche restano disponibili, ma non devono essere il principale punto visivo.

### 6.4 Dopo il caricamento della demo

La scheda di partenza diventa una checklist:

- documenti caricati;
- collegamenti creati;
- segnalazioni disponibili;
- apri il primo caso.

Il percorso non deve bloccare la navigazione.

### 6.5 Navigazione essenziale

Menu principale:

- Inizio;
- Documenti;
- Da controllare;
- Guida.

Menu Strumenti avanzati, chiuso per impostazione iniziale:

- Collegamenti;
- Regole proposte;
- Verifica delle regole;
- Registro attività;
- Utenti.

Il raggruppamento non modifica autorizzazioni e visibilità per ruolo.

## 7. Mappa terminologica

| Termine tecnico | Etichetta utente | Uso |
|---|---|---|
| Dashboard | Inizio | pagina di orientamento |
| Cases / Anomalie | Da controllare | possibili differenze |
| Chains | Collegamenti | documenti della stessa attività |
| Discovery / Autopilota | Regole proposte | controlli suggeriti |
| Validation Lab | Verifica delle regole | qualità e test |
| Audit | Registro attività | cronologia amministrativa |
| Proof Graph | Prove collegate | dettaglio, non menu |
| Confidence | Affidabilità della lettura | spiegazione contestuale |

I nomi interni, gli endpoint e i modelli dati non devono essere rinominati in questa fase.

## 8. Guida permanente

La guida integrata deve contenere:

1. che cos'è ThisTinti;
2. come iniziare in tre passaggi;
3. esempio dei 10, 8 e 10 pezzi;
4. spiegazione delle pagine;
5. differenza tra segnalazione e decisione;
6. uso dei documenti dimostrativi;
7. uso prudente dei documenti reali;
8. Local Edition e dati sul computer;
9. come riaprire gli strumenti avanzati;
10. collegamento alle note legali.

## 9. Stati vuoti

Ogni stato vuoto deve spiegare il prossimo passo.

### Documenti

“Nessun documento. Prova l'esempio oppure carica file autorizzati.”

### Collegamenti

“Nessun collegamento. Comparirà quando due o più documenti condivideranno riferimenti compatibili.”

### Da controllare

“Nessuna segnalazione. Può significare che non sono state trovate differenze oppure che i documenti disponibili non sono ancora sufficienti.”

### Regole proposte

“Nessuna regola proposta. Servono più documenti coerenti prima che ThisTinti possa suggerire controlli.”

## 10. Accessibilità

Requisiti minimi della fase:

- navigazione completa da tastiera;
- focus visibile;
- dialog con titolo accessibile;
- chiusura con Esc;
- nessun contenuto essenziale comunicato soltanto tramite colore;
- contrasto coerente con il tema esistente;
- rispetto di prefers-reduced-motion;
- ordine di tabulazione naturale;
- testi comprensibili senza icone;
- target interattivi adeguati anche su schermi piccoli.

Una verifica WCAG manuale indipendente resta un gate esterno e non viene dichiarata completata dal presente lavoro.

## 11. Sicurezza, privacy e aspetti legali

### Sicurezza

- il livello di esperienza viene caricato dopo il core applicativo;
- nessun accesso diretto a segreti o token;
- nessun HTML derivato da documenti inserito senza escaping;
- nessuna nuova origine di rete;
- nessun bypass dei ruoli;
- nessun account demo predefinito;
- nessun caricamento automatico.

### Privacy

- nessuna telemetria;
- nessun identificatore utente inviato fuori dall'installazione;
- preferenze di onboarding locali e non sensibili;
- esempi sintetici inclusi nel prodotto;
- avviso esplicito prima dell'uso di documenti reali.

### Linguaggio legale

Il prodotto deve essere descritto come strumento informativo e configurabile. Non deve suggerire che certifica documenti, adempimenti o decisioni.

## 12. Piano di implementazione

### Fase 0 — Fondazione

- separare il core frontend dal livello di esperienza;
- mantenere i controlli di sicurezza sul core;
- introdurre CSS e JavaScript dedicati all'onboarding;
- documentare il programma;
- aggiungere controlli automatici di regressione.

Criterio di uscita: core invariato e test esistenti verdi.

### Fase 1 — Comprensione immediata

- linguaggio pubblico neutro;
- guida permanente;
- introduzione al primo ingresso;
- stati vuoti istruttivi;
- presentazione visuale pre-accesso.

Criterio di uscita: percorso comprensibile senza documenti reali.

### Fase 2 — Navigazione progressiva

- menu essenziale;
- gruppo Strumenti avanzati;
- nuove etichette;
- gestione coerente di ruolo e vista attiva.

Criterio di uscita: nessuna funzione persa e navigazione completa da tastiera.

### Fase 3 — Primo risultato guidato

- scheda di partenza sulla Panoramica;
- checklist dopo la demo;
- collegamento diretto alla prima segnalazione;
- messaggi di completamento non invasivi.

Criterio di uscita: demo completabile in meno di tre minuti nei test moderati.

### Fase 4 — Prova pilota

- 5–10 tester senza addestramento;
- raccolta manuale delle osservazioni;
- nessuna telemetria;
- correzione dei punti di blocco;
- nuova build Windows separata dalla RC1 già verificata.

Criterio di uscita: soglie di comprensione e completamento raggiunte.

### Fase 5 — Modelli locali

Soltanto dopo la validazione dell'onboarding:

- Acquisti e fornitori;
- Logistica e consegne;
- Resi e note di credito;
- Commessa semplice.

I modelli non devono comparire nel primo percorso finché l'utente non ha completato o chiuso la guida iniziale.

## 13. Strategia di pubblicazione

### Canale

Pubblicare come Public Preview, non come beta validata.

### Percorso pubblico

1. pagina ufficiale;
2. download Windows;
3. installazione;
4. anteprima visuale;
5. creazione dello spazio locale;
6. demo sintetica;
7. eventuale caricamento di file autorizzati.

### Soft launch

La prima diffusione deve essere personale e limitata. Il tester riceve soltanto il link ufficiale e non istruzioni aggiuntive. L'assenza di aiuto è parte del test.

### Messaggio pubblico

> Carica documenti collegati. ThisTinti li mette in ordine e ti mostra cosa controllare.

## 14. Protocollo di prova utente

Ogni sessione deve registrare manualmente:

- tempo installazione;
- tempo creazione spazio;
- tempo caricamento demo;
- tempo apertura prima segnalazione;
- punti di esitazione;
- parole non comprese;
- errori;
- richiesta spontanea di aiuto;
- spiegazione finale del prodotto.

Domande finali:

1. A cosa serve ThisTinti?
2. Che cosa significa “Da controllare”?
3. ThisTinti decide quale documento è corretto?
4. Dove rimangono i dati nella Local Edition?
5. Quale sarebbe il tuo prossimo passo?

## 15. Gate di rilascio della nuova esperienza

La nuova build non deve essere pubblicata finché non sono soddisfatti tutti i gate interni:

- test Python verdi;
- sintassi JavaScript valida;
- nessuna regressione CSRF;
- nessun token nel web storage;
- struttura del menu verificata;
- dialog accessibili strutturalmente;
- demo sintetica funzionante;
- installazione e aggiornamento Windows verificati;
- persistenza dei dati esistenti verificata;
- disinstallazione verificata;
- testo legale coerente;
- stato Public Preview mantenuto.

I gate esterni già documentati restano invariati.

## 16. Fuori perimetro

Non fanno parte del programma corrente:

- SaaS ThisTinti;
- app mobile;
- telemetria;
- account dimostrativi condivisi;
- sincronizzazione cloud;
- integrazioni bancarie, PEC o gestionali;
- interpretazione fiscale o legale;
- marketplace di modelli;
- modifiche al motore di matching;
- automazioni operative aggiuntive.

## 17. Regola per le decisioni future

Una nuova funzione può entrare nel percorso iniziale soltanto quando risponde sì a tutte queste domande:

1. aiuta l'utente a ottenere il primo risultato?
2. è comprensibile senza formazione?
3. non richiede un nuovo servizio da mantenere?
4. non aumenta in modo sostanziale rischi legali, privacy o sicurezza?
5. può essere testata automaticamente?
6. può essere rimossa senza alterare il motore?

In caso contrario deve restare avanzata, sperimentale o fuori prodotto.
