# Diagnostica locale integrata

La pagina `/diagnostics.html` sostituisce i runner esterni usati durante il collaudo RC7 con un flusso locale, visibile e tracciabile dentro ThisTinti.

## Accesso

Dopo l'accesso, la voce **Diagnostica** compare nella navigazione dell'app. La pagina usa la sessione corrente e non invia dati a servizi esterni.

## Controlli sicuri

**Esegui controlli sicuri** verifica:

- disponibilità del servizio e versione OpenAPI;
- sessione e dashboard;
- lettura di documenti, catene, segnalazioni e attività;
- struttura minima dei collegamenti e presenza di spiegazioni/evidenze;
- assenza di overflow orizzontale globale nella pagina diagnostica;
- presenza di controlli raggiungibili da tastiera;
- persistenza locale del browser.

Questi controlli sono di sola lettura, salvo una scrittura temporanea in `localStorage` immediatamente rimossa.

## Test attivo di recupero errore

**Esegui anche test recupero errore** aggiunge un documento JSON diagnostico con quantità testuale `cinque`. Il test:

1. usa lo stesso endpoint di caricamento dell'interfaccia;
2. applica cookie di sessione, CSRF e chiave di idempotenza;
3. attende il job persistente;
4. richiede che l'input sia rifiutato o classificato `parse_failed`;
5. verifica che campo, valore e motivo siano consultabili nel risultato.

Il documento e il job diagnostici restano intenzionalmente tracciabili in **Attività**. Non vengono creati valori economici validi e non viene eseguita alcuna decisione automatica.

## Verbale

La pagina produce un JSON con:

- schema e modalità del test;
- data di avvio e fine;
- versione osservata;
- stato, dettaglio, durata e dati tecnici di ogni controllo;
- dati aggregati osservati;
- esito complessivo `PASS`, `PARZIALE` o `FAIL`.

`SKIPPED` e `PARTIAL` non vengono trasformati in `PASS`.

## Limiti

La diagnostica integrata non sostituisce:

- verifica umana con NVDA o altra tecnologia assistiva;
- pilot su documenti reali autorizzati e anonimizzati;
- firma Authenticode;
- revisione indipendente legale, privacy e sicurezza;
- prova manuale di aggiornamento, riavvio Windows e disinstallazione.

Non costituisce certificazione, autorizzazione alla produzione o misura indipendente dell'accuratezza del motore.
