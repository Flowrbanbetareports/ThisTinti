# RC12 — collaudo umano end-to-end

Versione di riferimento: `3.4.0-alpha.7-rc.12`.

Questo collaudo serve a verificare l'esperienza reale della Public Preview installata su Windows. Non sostituisce pilot documentale, penetration test, revisione legale o collaudo professionale WCAG.

## Obiettivo

Determinare se un utente può installare, aprire, comprendere e usare ThisTinti senza interventi tecnici esterni e registrare qualsiasi difetto che giustifichi una RC13.

## A. Installazione e primo avvio

1. Scaricare l'installer ufficiale RC12.
2. Verificare che il file sia `ThisTinti-Setup-3.4.0-alpha.7-rc.12-x64.exe`.
3. Completare l'installazione senza strumenti da sviluppatore.
4. Avviare ThisTinti dal collegamento creato dall'installer.
5. Verificare che il browser apra l'app locale e che API e worker risultino disponibili.
6. Annotare avvisi Windows, tempi anomali o passaggi non comprensibili.

## B. Navigazione iniziale

Verificare almeno:

- Centro operativo;
- Pratiche e segnalazioni;
- Attività;
- Diagnostica;
- Progetto e piani;
- guida o onboarding disponibile;
- eventuali schermate di amministrazione accessibili al ruolo corrente.

Nessun menu deve produrre errore, pagina vuota inattesa o terminologia evidentemente tecnica senza spiegazione.

## C. Flusso documentale demo

1. Caricare o ripristinare il dataset demo previsto dall'app.
2. Attendere la conclusione dei job.
3. Aprire la pratica prioritaria proposta dal Centro operativo.
4. Aprire almeno una segnalazione per tipologia disponibile.
5. Risalire dalla segnalazione alla prova, alla riga estratta e al documento originale.
6. Verificare che valori, severità e motivazioni siano comprensibili.

## D. Correzione supervisionata

1. Selezionare una riga estratta correggibile.
2. Modificare un valore con motivazione esplicita.
3. Verificare storico prima/dopo e autore della correzione.
4. Verificare la rianalisi delle catene collegate.
5. Confermare che il dato originale resti ricostruibile e che l'audit non venga sovrascritto.

## E. Attività e recupero

- verificare stato dei job;
- aprire dettagli ed errori;
- provare retry quando disponibile;
- provare cancellazione su un job sicuro;
- chiudere e riaprire ThisTinti;
- verificare che attività e dati persistano correttamente.

## F. Diagnostica

1. Aprire **Diagnostica**.
2. Eseguire i controlli sicuri.
3. Nessun controllo diverso da quelli deliberatamente non eseguiti deve risultare `FAIL` senza spiegazione.
4. Se autorizzato, eseguire anche il test di integrità numerica.
5. Scaricare il verbale JSON.

## G. Progetto e piani

Verificare che:

- la pagina sia chiaramente separata dal lavoro documentale;
- Integration Pack sia scaricabile soltanto dal ruolo previsto;
- checkout risulti disattivato;
- sponsor risulti disattivato;
- nessuna funzione faccia credere che ThisTinti sia un SaaS o che invii documenti all'autore;
- le metriche pubbliche non vengano descritte come utenti o installazioni attive.

## H. Persistenza, aggiornamento e disinstallazione

- chiudere completamente l'app e riaprirla;
- verificare documenti, pratiche, correzioni e audit;
- quando esiste una release successiva, provare aggiornamento sopra RC12 senza cancellare i dati;
- verificare che la disinstallazione standard non elimini implicitamente i dati;
- verificare che la cancellazione definitiva, quando richiesta, richieda un'azione esplicita.

## I. Accessibilità e usabilità manuale

Ripetere le schermate principali con zoom 125%, 150% e 200%:

- nessun controllo essenziale deve diventare irraggiungibile;
- il testo deve restare leggibile;
- il focus da tastiera deve essere visibile;
- il flusso principale deve poter essere percorso con `Tab`, `Shift+Tab`, `Enter` e `Space` quando appropriato.

Se disponibile, provare almeno una sessione con NVDA e annotare elementi ambigui o non annunciati.

## J. Criterio per RC13

Creare una RC13 soltanto se dal collaudo emerge almeno una delle seguenti condizioni:

- bug riproducibile;
- perdita o corruzione di dati;
- risultato documentale scorretto o fuorviante;
- flusso essenziale non comprensibile a un nuovo utente;
- problema di accessibilità o navigazione che blocca un'azione importante;
- debito architetturale necessario per correggere in modo sicuro un difetto reale.

Nuove funzioni non richieste dal collaudo non sono una ragione sufficiente per RC13.

## Evidenze da conservare

Per ogni problema:

- schermata o breve video;
- passaggi per riprodurlo;
- risultato atteso;
- risultato osservato;
- gravità stimata;
- versione esatta;
- eventuale verbale diagnostico associato.

Ogni difetto importante corretto deve diventare, quando tecnicamente possibile, un test di regressione automatico.
