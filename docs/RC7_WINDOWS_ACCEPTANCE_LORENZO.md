# Collaudo manuale RC7 su Windows — Lorenzo

Questo collaudo completa le verifiche automatiche senza sostituirle. Va eseguito
sull’installer RC7 associato al commit candidato e al workflow Windows indicati
nel registro RC7. Non usare documenti aziendali non autorizzati.

## Preparazione ed evidenza

1. Scaricare installer, file `.sha256`, `release-provenance.json` e guida
   `VERIFY-THIS-DOWNLOAD.md` dallo stesso candidato.
2. In PowerShell eseguire:

   ```powershell
   Get-FileHash .\ThisTinti-Setup-3.4.0-alpha.7-rc.7-x64.exe -Algorithm SHA256
   ```

3. Confrontare l’hash con il file `.sha256` e con la provenienza.
4. Annotare versione Windows, browser e versione browser. Salvare screenshot,
   hash e risultati in una cartella con data e commit candidato.

Esito positivo: i tre riferimenti coincidono. Un avviso “Editore sconosciuto” è
atteso finché non esiste una firma Authenticode; qualunque altro errore blocca il
rilascio.

## Aggiornamento e conservazione

1. Con RC5 o RC6 installata, creare uno spazio locale e caricare i documenti di
   esempio. Annotare documenti, collegamenti e numero di segnalazioni.
2. Chiudere ThisTinti e installare RC7 nella stessa destinazione.
3. Avviare RC7, accedere allo spazio esistente e controllare che documenti,
   collegamenti, attività e segnalazioni siano presenti.
4. Riavviare Windows e ripetere il controllo.

Esito positivo: nessuna richiesta di ricreare lo spazio, nessun dato mancante,
nessuna rielaborazione silenziosa e versione RC7 visibile.

## Percorso Carica → Collega → Controlla

1. Caricare l’esempio ufficiale senza usare terminale o API.
2. Aprire **Collegamenti**, espandere una catena con `Tab` e `Invio`, leggere
   percentuale e motivazione della proposta, quindi collegare e scollegare.
3. Aprire **Da controllare**, scegliere prima un caso `critical`, aprire
   documento originale e riga estratta.
4. Tornare alla lista e verificare che filtro, conteggio e ordine `critical`
   restino coerenti.

Esito positivo: il percorso è comprensibile senza istruzioni verbali; ogni
segnalazione porta all’evidenza e all’originale; nessun comando economico o di
approvazione automatica è presentato.

## Recupero errori

1. Caricare un JSON con quantità testuale non numerica.
2. Verificare un errore persistente con documento, riga, campo, valore e motivo;
   il dato non deve comparire come zero.
3. In **Attività**, cercare il job, aprire i dettagli, correggere i metadati
   consentiti e avviare la rielaborazione.
4. Chiudere e riaprire l’app; stato ed errore devono restare consultabili.

Esito positivo: nessun HTTP 500 visibile, nessuna perdita dell’ultima estrazione
valida, nuovo tentativo tracciato e risultato persistente.

## Zoom, tastiera e leggibilità

Ripetere **Attività**, **Collegamenti** e **Da controllare** a zoom browser 125%,
150% e 200%, usando una finestra non massimizzata.

- usare solo `Tab`, `Maiusc+Tab`, frecce, `Invio`, `Spazio`, `Esc`, `Home` e
  `Fine`;
- verificare focus sempre visibile, etichette complete e ordine prevedibile;
- controllare che menu e pagina non coprano i contenuti;
- accettare lo scorrimento orizzontale dentro una tabella larga, non sull’intera
  pagina;
- attivare “Riduci animazioni” in Windows e verificare che nessun passaggio
  dipenda dal movimento.

Ripetere almeno il percorso principale con NVDA e Chrome o Firefox, annotando
nome, ruolo e stato annunciati per navigazione, dialoghi, errori e pulsanti.

Esito positivo: nessun controllo irraggiungibile, testo sovrapposto o focus
perduto; gli errori sono annunciati e comprensibili senza il solo colore.

## Disinstallazione

1. Chiudere ThisTinti e disinstallarlo.
2. Verificare che l’applicazione sia rimossa.
3. Verificare che la cartella dati locale sia conservata.
4. Reinstallare RC7 e controllare che lo spazio possa essere riaperto.

Esito positivo: programma rimosso, dati conservati e riutilizzabili.

## Verbale minimo

Per ogni sezione registrare `PASS`, `FAIL` o `NON ESEGUITO`, procedura, risultato,
screenshot e note. Un `FAIL` su hash, aggiornamento, persistenza, dati numerici,
accesso alle evidenze o tastiera blocca la pubblicazione. `NON ESEGUITO` non può
essere trasformato in `PASS`.
