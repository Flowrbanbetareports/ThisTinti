# Accettazione RC8 direttamente in ThisTinti

Questa prova si svolge dall’app installata. Non richiede PowerShell, terminale
o runner esterni.

## Preparazione

1. Installare la candidata RC8 sopra la RC7, senza cancellare cartelle dati.
2. Avviare ThisTinti e accedere al proprio spazio locale.
3. Verificare che documenti, collegamenti, segnalazioni e attività precedenti
   siano ancora presenti.
4. Aprire **Diagnostica** dal menu.

## Controlli sicuri

1. Selezionare **Esegui controlli sicuri**.
2. Attendere la conclusione senza cambiare pagina.
3. L’esito complessivo atteso è `PARZIALE`, perché il test numerico deve restare
   `NON ESEGUITO` finché non viene autorizzato esplicitamente.
4. Nessun altro controllo deve risultare `FAIL`.

## Test di integrità numerica

1. Selezionare **Esegui anche test integrità numerica**.
2. Attendere la conclusione del job persistente.
3. Con un utente `admin` o `reviewer`, l’esito atteso è `PASS`.
4. Il controllo numerico deve dichiarare che il valore `cinque` è stato
   rifiutato con campo e motivo consultabili.
5. Aprire **Attività** e verificare che il job diagnostico sia tracciabile.
6. Scaricare il verbale JSON dalla schermata Diagnostica e conservarlo insieme
   agli screenshot del collaudo.

## Prova visiva e tastiera

Ripetere la schermata Diagnostica a zoom browser 125%, 150% e 200%:

- nessun testo o pulsante deve uscire dalla pagina;
- la tabella può scorrere nel proprio contenitore, non l’intera pagina;
- stato e dettagli devono restare leggibili;
- con il solo tasto `Tab` devono essere raggiungibili ritorno all’app, due
  azioni di test, download e copia;
- il focus deve essere sempre visibile;
- con riduzione animazioni attiva in Windows non devono comparire movimenti
  indispensabili alla comprensione.

Se disponibile, ripetere titoli, pulsanti, stati e tabella con NVDA. Annotare
qualsiasi elemento letto in modo ambiguo o non raggiungibile.

## Esito

Il collaudo è superato soltanto se:

- non esistono `FAIL` inspiegati;
- il test numerico attivo è `PASS` per un ruolo autorizzato;
- dati precedenti e originali sono conservati;
- zoom e tastiera non bloccano il flusso;
- il verbale JSON viene scaricato correttamente.

Inviare il verbale JSON e gli eventuali screenshot. La diagnostica non sostituisce
pilot documentale, pentest, firma Authenticode o revisione professionale WCAG.
