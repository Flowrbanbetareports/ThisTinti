# Protocollo di validazione su documenti reali

## Obiettivo

Stabilire se ThisTinti è affidabile per uno specifico contesto aziendale senza confondere il funzionamento tecnico con l'accuratezza operativa.

## Campione minimo consigliato

Per ogni settore o gestionale:

- almeno 100 catene documentali complete;
- almeno 500 righe prodotto;
- ordini con consegne parziali;
- più fatture per lo stesso ordine;
- resi e note di credito;
- documenti corretti e documenti con anomalie note;
- formati e fornitori differenti.

I dati devono essere anonimizzati o trattati in un ambiente autorizzato.

## Ground truth

Due revisori umani qualificati classificano indipendentemente:

- collegamento corretto dei documenti;
- anomalie effettive;
- importo corretto;
- gravità;
- casi non determinabili.

Le divergenze tra revisori vengono risolte prima del confronto con il software.

## Metriche

### Parsing

- percentuale documenti interpretati;
- percentuale righe estratte correttamente;
- accuratezza di quantità, prezzo, sconto e totale;
- tasso di fallimento esplicito.

### Matching

- precisione dei collegamenti automatici;
- richiamo dei collegamenti corretti;
- percentuale documenti lasciati prudentemente scollegati;
- collegamenti errati silenziosi — obiettivo: zero nel campione.

### Anomalie

- veri positivi;
- falsi positivi;
- falsi negativi;
- precisione = veri positivi / segnalazioni;
- richiamo = veri positivi / anomalie reali;
- errore medio sull'importo.

### Intelligence preventiva

- precisione dei documenti mancanti previsti;
- accuratezza delle scadenze previste;
- calibrazione fra confidenza dichiarata e risultati corretti;
- falsi blocchi e approvazioni rischiose non bloccate;
- copertura del self-red-team per famiglia di errore;
- stabilità del processo dominante e dei pattern anonimi.

### Operazioni

- tempo umano prima/dopo;
- numero di revisioni manuali;
- tempo medio per fascicolo;
- disponibilità e latenza;
- tasso di rielaborazione fallita.

## Soglie preliminari

Le soglie vanno concordate per rischio e settore. Come criterio prudente per un pilot:

- zero contaminazioni tra tenant;
- zero azioni esterne automatiche;
- `safe_to_automate=false` finché il gate reale non è approvato;
- 100% tracciabilità delle prove;
- almeno 99% accuratezza dei campi economici sui documenti strutturati;
- almeno 95% precisione dei casi ad alta confidenza;
- collegamenti incerti sottoposti a revisione;
- nessun errore critico non rilevato nel campione.

Queste soglie non sono una certificazione legale o contabile.

## Esito

Il pilot deve produrre un rapporto con:

- dataset e perimetro;
- errori per formato e fornitore;
- metriche complete;
- modifiche alle regole;
- rischi residui;
- decisione: non idoneo, idoneo con revisione, idoneo per il perimetro validato.

## Implementazione nel Validation Lab

La versione 3.2 include un laboratorio eseguibile dall'interfaccia o da CLI. Il formato della suite contiene:

- nome e versione;
- soglie del gate;
- scenari indipendenti;
- documenti JSON strutturati;
- elenco delle anomalie attese con importo e tolleranza;
- tipi di risultato eventualmente ignorabili.

Il matching tra risultato atteso e osservato è uno-a-uno per tipo e importo. I risultati inattesi sono falsi positivi; quelli attesi ma non trovati sono falsi negativi. Se la suite non supera il gate, `scripts/run_validation_gate.py` termina con codice diverso da zero.

La suite predefinita in `samples/validation_core.json` è intenzionalmente sintetica e riproducibile. Non deve essere usata per dichiarare accuratezza commerciale.

## Regole implementate per l'idoneità all'automazione

Il gate sintetico incluso nel repository dimostra regressione e riproducibilità, non accuratezza commerciale. L'idoneità operativa richiede cumulativamente:

- dataset attivo con `evidence_level` pari a `anonymized_pilot` o `production`;
- almeno 30 scenari nel run;
- gate superato;
- `engine_version` uguale alla release in esecuzione;
- approvazione esplicita di un amministratore sul run esatto, con motivazione, data e audit;
- rischio della singola pratica basso e confidenza minima dei documenti almeno 0,90.

L'endpoint `POST /api/validation/datasets/{dataset_id}/automation` registra approvazione o revoca. Ogni nuova esecuzione sul dataset imposta nuovamente `automation_eligible=false`. Un test sintetico successivo non oscura un pilot reale già approvato appartenente a un altro dataset. I vincoli del database impediscono approvazioni sintetiche o prive delle relative evidenze amministrative.
