# RC13 — collaudo umano end-to-end della Public Preview

Versione di riferimento: `3.4.0-alpha.7-rc.13`.

Questo collaudo verifica l'esperienza reale della Public Preview installata su Windows. Non sostituisce pilot documentale, penetration test, revisione legale/privacy o collaudo professionale WCAG.

## Identità da verificare prima del test

- release: `v3.4.0-alpha.7-rc.13`;
- installer: `ThisTinti-Setup-3.4.0-alpha.7-rc.13-x64.exe`;
- SHA-256: `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`;
- commit di rilascio: `f7609b51aec4c358d0410ca8ff83e60485cac96c`.

## Obiettivo

Determinare se una persona può installare, aprire, comprendere e usare ThisTinti senza interventi tecnici esterni e registrare ogni difetto riproducibile. RC13 è nata come hotfix di sicurezza PDF; questo protocollo riprende e aggiorna il collaudo umano che era stato predisposto sulla RC12.

## A. Installazione e primo avvio

1. Scaricare l'installer ufficiale RC13 dalla release GitHub.
2. Controllare nome file e, preferibilmente, SHA-256.
3. Completare l'installazione senza strumenti da sviluppatore.
4. Annotare eventuale avviso Windows relativo all'assenza di firma Authenticode; non interpretarlo come prova di malware né come firma valida.
5. Avviare ThisTinti dal collegamento creato dall'installer.
6. Verificare che il browser apra l'app locale e che API e worker risultino disponibili.
7. Annotare tempi anomali, errori o passaggi non comprensibili.

## B. Primo spazio locale e navigazione

Verificare almeno:

- creazione/accesso allo spazio locale;
- Centro operativo;
- Documenti;
- Catene/Pratiche e segnalazioni;
- Attività;
- Diagnostica;
- Progetto e piani;
- guida/onboarding;
- schermate amministrative accessibili al ruolo corrente.

Nessuna voce essenziale deve produrre errore, pagina vuota inattesa o terminologia incomprensibile senza spiegazione.

## C. Flusso documentale demo

1. Usare **Carica esempio** o il dataset demo previsto dall'app.
2. Attendere la conclusione dei job reali.
3. Aprire la pratica prioritaria proposta dal Centro operativo.
4. Aprire almeno una segnalazione disponibile.
5. Risalire dalla segnalazione alla prova, alla riga estratta e al documento originale.
6. Controllare che valori, severità e motivazioni siano comprensibili e coerenti.
7. Verificare che una segnalazione non venga presentata come decisione, certificazione o autorizzazione economica.

## D. Correzione supervisionata

1. Selezionare una riga estratta correggibile.
2. Modificare un valore con motivazione esplicita.
3. Verificare storico prima/dopo, autore e provenienza.
4. Verificare la rianalisi delle catene collegate.
5. Confermare che il dato originale resti ricostruibile e che l'audit non venga sovrascritto.

## E. Attività, retry e persistenza

- verificare stato dei job;
- aprire dettagli ed errori;
- provare retry quando disponibile;
- provare cancellazione solo su un job sicuro;
- chiudere completamente e riaprire ThisTinti;
- verificare che attività, documenti, pratiche, correzioni e audit persistano.

## F. Diagnostica

1. Aprire **Diagnostica**.
2. Eseguire i controlli sicuri.
3. Nessun controllo eseguito deve risultare `FAIL` senza spiegazione riproducibile.
4. Se previsto dall'interfaccia, eseguire il test attivo di integrità numerica.
5. Scaricare il verbale JSON.
6. Conservare il verbale insieme alla versione e all'orario del test in caso di difetto.

## G. Progetto e piani

Verificare che:

- la pagina sia chiaramente separata dal lavoro documentale;
- checkout e sponsor risultino inattivi;
- nessuna funzione faccia credere che ThisTinti sia un SaaS o invii documenti all'autore;
- le metriche GitHub siano descritte come download di asset e non come utenti/installazioni attive;
- eventuali collegamenti al pacchetto di integrazione o self-hosted siano coerenti con il ruolo e con il perimetro dichiarato.

## H. Aggiornamento, backup e disinstallazione

Quando tecnicamente possibile sul PC di prova:

- provare aggiornamento da una Public Preview precedente a RC13 e verificare la conservazione dati;
- eseguire backup e verifica del backup;
- eseguire un restore in destinazione di prova senza sovrascritture implicite;
- verificare che la disinstallazione standard non elimini implicitamente i dati locali;
- verificare che una cancellazione definitiva richieda un'azione esplicita.

## I. Accessibilità e usabilità manuale

Ripetere le schermate principali con zoom 125%, 150% e 200%:

- nessun controllo essenziale deve diventare irraggiungibile;
- il testo deve restare leggibile;
- il focus da tastiera deve essere visibile;
- il flusso principale deve poter essere percorso con `Tab`, `Shift+Tab`, `Enter`, `Space` e tasti freccia dove appropriato;
- non devono esserci trap di tastiera.

Eseguire almeno uno spot check con una tecnologia assistiva reale, preferibilmente NVDA su Windows, annotando controlli non annunciati, etichette ambigue, ordine di lettura incoerente o stati non comunicati.

## J. Sessioni con utenti non istruiti

Per ogni sessione, senza spiegare preventivamente il funzionamento oltre alle istruzioni pubbliche:

1. chiedere alla persona di descrivere in una frase cosa pensa faccia ThisTinti;
2. farle installare/aprire il programma;
3. farle creare lo spazio locale;
4. chiederle di usare la demo;
5. chiederle di trovare una cosa “da controllare” e risalire alla prova;
6. registrare dove chiede aiuto o interpreta male il prodotto.

Target dell'onboarding: almeno 8 persone su 10, quando si raggiunge un campione di 10, devono riuscire a spiegare correttamente il prodotto e raggiungere la prima evidenza senza assistenza bloccante.

## K. Classificazione dei difetti

### Bloccante

Perdita/corruzione dati, impossibilità di installare/avviare, risultato documentale gravemente fuorviante senza avviso, bypass di sicurezza o impossibilità di recuperare l'evidenza.

### Serio

Flusso principale incompletabile, persistente errore di worker/retry, problema di accessibilità che impedisce un'azione essenziale, dati o audit incoerenti.

### Medio

Errore riproducibile con workaround ragionevole, terminologia significativamente ambigua, layout problematico ma non bloccante.

### Minore

Difetto cosmetico o di rifinitura senza impatto sulla correttezza, sicurezza o completamento del flusso.

## Evidenze da conservare

Per ogni problema:

- schermata o breve video;
- passaggi esatti per riprodurlo;
- risultato atteso;
- risultato osservato;
- gravità stimata;
- versione esatta;
- eventuale verbale Diagnostica;
- eventuale file di prova, solo se autorizzato e non sensibile.

Ogni difetto importante corretto deve diventare, quando tecnicamente possibile, un test di regressione automatico.

## Criterio di chiusura

Il collaudo RC13 può essere dichiarato completato soltanto quando:

- tutti i passaggi applicabili sono stati eseguiti realmente;
- non restano difetti bloccanti o seri irrisolti;
- le evidenze dei problemi sono state conservate;
- i problemi corretti sono coperti da regressioni quando possibile;
- tastiera e tecnologia assistiva sono state provate da persone reali;
- le sessioni con utenti non istruiti previste dal gate onboarding sono state documentate.
