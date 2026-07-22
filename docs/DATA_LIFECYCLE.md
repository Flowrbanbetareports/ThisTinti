# Ciclo di vita dei dati

## Principio generale

La Local Edition conserva database, documenti, quarantena, log operativi e backup sul computer dell'utilizzatore. La distribuzione ufficiale non invia questi contenuti all'autore e non richiede un account centrale.

## Posizione dei dati su Windows

L'installazione standard usa:

- programma: `%LOCALAPPDATA%\Programs\ThisTinti`;
- dati locali: `%LOCALAPPDATA%\ThisTinti`.

La cartella dati può contenere informazioni aziendali. Non deve essere condivisa, sincronizzata o caricata pubblicamente senza autorizzazione e anonimizzazione.

## Backup

Prima di aggiornamenti importanti, migrazioni, ripristini o cancellazioni:

1. chiudere ThisTinti;
2. creare un backup dall'applicazione o con gli strumenti inclusi;
3. verificare l'archivio prodotto;
4. conservare almeno una copia separata dal computer principale.

Un backup non verificato non è considerato una protezione sufficiente.

## Disinstallazione

La disinstallazione rimuove il programma, ma conserva deliberatamente `%LOCALAPPDATA%\ThisTinti`. Questa scelta riduce il rischio di perdere documenti e database per errore e permette una successiva reinstallazione.

## Cancellazione completa

Per eliminare definitivamente i dati locali:

1. esportare o creare un backup, quando necessario;
2. chiudere l'applicazione e verificare che i relativi processi non siano attivi;
3. disinstallare ThisTinti;
4. eliminare manualmente `%LOCALAPPDATA%\ThisTinti`;
5. svuotare il Cestino o applicare la procedura aziendale di cancellazione sicura;
6. eliminare separatamente eventuali backup, copie sincronizzate e archivi esportati.

La cancellazione della cartella dati è irreversibile e non viene eseguita automaticamente dall'uninstaller.

## Conservazione e responsabilità

ThisTinti non impone una durata universale di conservazione. L'organizzazione che usa il software deve definire:

- quali documenti sono necessari;
- per quanto tempo conservarli;
- chi può accedervi;
- quando e come cancellarli;
- come gestire richieste degli interessati, incidenti e obblighi normativi.

## Self-hosted

Nella Self-Hosted Reference Edition database, storage, quarantena, backup e log risiedono nell'infrastruttura scelta dall'operatore. Percorsi, cifratura, retention, copie off-site e cancellazione dipendono dalla configurazione reale e devono essere documentati prima dell'uso con dati sensibili.
