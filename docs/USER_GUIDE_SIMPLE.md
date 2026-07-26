# Guida semplice per l'utilizzatore

## Local Free Edition

1. Scaricare l'installer e il checksum dalla release ufficiale.
2. Verificare il checksum SHA-256.
3. Leggere e accettare licenza e avvisi.
4. Installare e aprire ThisTinti.
5. Creare lo spazio aziendale e l'amministratore locale.
6. Caricare copie dei documenti, conservando sempre gli originali.
7. Verificare manualmente ogni anomalia e ogni collegamento proposto.

## Cosa fa

ThisTinti collega documenti della stessa operazione, segnala possibili incongruenze,
mostra documenti mancanti e produce spiegazioni verificabili.

## Cosa non fa

- non autorizza pagamenti;
- non sostituisce contabilità, consulenza fiscale o legale;
- non garantisce che ogni errore venga rilevato;
- non conserva copie esterne dei dati;
- non fornisce assistenza o SLA garantiti.

## Backup

Usare il comando di backup integrato prima di aggiornamenti importanti. Conservare almeno
una copia su un supporto separato e provare periodicamente il ripristino.

## Aggiornamento

1. Creare un backup.
2. Leggere le note di rilascio.
3. Verificare checksum e provenienza.
4. Installare la nuova versione.
5. Controllare una pratica campione prima di riprendere l'uso normale.

## Disinstallazione

La disinstallazione del programma non deve essere usata come metodo di cancellazione dei
dati. L'archivio aziendale va individuato, esportato o eliminato consapevolmente dal
titolare del sistema.

## Problemi

Il progetto non garantisce supporto. Un'organizzazione può usare la documentazione,
aprire una segnalazione pubblica priva di dati sensibili o incaricare tecnici propri.

## Attività ed errori recuperabili

La pagina **Attività** conserva lo stato dei caricamenti, delle rielaborazioni e delle
analisi anche dopo la chiusura di un messaggio temporaneo. Da questa pagina è possibile:

- filtrare e cercare le elaborazioni;
- leggere l'errore completo e il numero di tentativi;
- annullare un'attività ancora in attesa;
- riprovare un'attività fallita quando il file o il documento sono ancora disponibili;
- aprire direttamente il documento collegato.

Un errore non va considerato risolto soltanto perché viene riprovato. Verificare il nuovo
risultato e confrontarlo con il file originale.

## Correzione e rielaborazione

Nel dettaglio di un documento, un amministratore o revisore può usare **Correggi e
rielabora** per indicare tipo, numero, fornitore e data corretti. La rielaborazione viene
messa nella coda persistente. Se il nuovo tentativo fallisce, l'ultima estrazione valida
non viene distrutta e l'errore resta consultabile nella pagina Attività.

## Verifica e correzione dei collegamenti

Nel dettaglio di una catena, la sezione **Documenti collegati** mostra per ogni file il
ruolo, l'affidabilità e il motivo del collegamento. **Collegamenti proposti** elenca
separatamente documenti non ancora collegati e li ordina per compatibilità.

Le percentuali sono indicazioni tecniche, non approvazioni. Prima di usare **Collega** o
**Scollega**, aprire il documento e confrontare il file originale. Ogni modifica manuale
viene registrata nell'audit e provoca una nuova analisi della catena; le segnalazioni
possono quindi cambiare.
