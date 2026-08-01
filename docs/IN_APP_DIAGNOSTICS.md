# Diagnostica locale integrata

La pagina `/diagnostics.html` sostituisce i runner esterni usati durante il collaudo RC7 con un flusso locale, visibile e tracciabile dentro ThisTinti.

## Accesso

Dopo l'accesso, la voce **Diagnostica** compare nella navigazione dell'app. La pagina usa la sessione corrente e non invia dati a servizi esterni.

## Controlli sicuri

**Esegui controlli sicuri** verifica:

- disponibilità del servizio e coerenza tra versione runtime e OpenAPI;
- sessione, ruolo e dashboard;
- lettura di documenti, catene, segnalazioni e attività;
- struttura minima dei collegamenti e presenza di spiegazioni/evidenze;
- assenza di overflow orizzontale globale nella pagina diagnostica;
- struttura minima dei controlli predisposti per il focus da tastiera;
- persistenza locale del browser.

Questi controlli sono di sola lettura, salvo una scrittura temporanea in `localStorage` immediatamente rimossa.

La verifica della struttura di focus non sostituisce una prova umana con la sola tastiera.

## Test attivo di integrità numerica

**Esegui anche test integrità numerica** aggiunge un documento JSON diagnostico con quantità testuale `cinque`. Il test:

1. usa lo stesso endpoint di caricamento dell'interfaccia;
2. applica cookie di sessione, CSRF e chiave di idempotenza;
3. attende il job persistente;
4. richiede che l'input sia rifiutato o classificato `parse_failed`;
5. verifica che campo, valore e motivo siano consultabili nel risultato.

Il documento e il job diagnostici restano intenzionalmente tracciabili in **Attività**. Non vengono creati valori economici validi e non viene eseguita alcuna decisione automatica.

Il test richiede un ruolo `admin` o `reviewer`. Con un ruolo di sola consultazione resta `NON ESEGUITO`; un mancato permesso non viene presentato come difetto del motore.

## Verbale

La pagina produce un JSON con:

- schema e modalità del test;
- data di avvio e fine;
- versione osservata;
- stato, dettaglio, durata e dati tecnici di ogni controllo;
- dati aggregati osservati;
- esito complessivo `PASS`, `PARZIALE` o `FAIL`;
- controlli intenzionalmente omessi marcati `NON ESEGUITO`.

`NON ESEGUITO` e `PARZIALE` non vengono trasformati in `PASS`.

## Limiti

La diagnostica integrata non sostituisce:

- verifica umana con NVDA o altra tecnologia assistiva;
- pilot su documenti reali autorizzati e anonimizzati;
- firma Authenticode;
- revisione indipendente legale, privacy e sicurezza;
- prova manuale di aggiornamento, riavvio Windows e disinstallazione.

Non costituisce certificazione, autorizzazione alla produzione o misura indipendente dell'accuratezza del motore.
