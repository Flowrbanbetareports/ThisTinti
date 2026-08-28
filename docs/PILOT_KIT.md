# Kit per il primo pilot aziendale

## Obiettivo

Misurare se ThisTinti è utile su documenti reali senza trasformare il pilot in una dimostrazione costruita sugli stessi casi usati per calibrare il sistema.

Per Procurement, la baseline operativa è `docs/PROCUREMENT_PILOT_PROTOCOL.md` e il relativo toolkit `scripts/procurement_pilot_protocol.py`.

## Configurazione consigliata

- installazione locale o self-hosted gestita dall'azienda;
- nessun documento aziendale aggiunto al repository pubblico;
- documenti anonimizzati quando richiesto dal perimetro autorizzato;
- automazioni esterne disabilitate;
- controllo umano obbligatorio;
- procedura alternativa disponibile se il programma non funziona.

## Campione Procurement

Il primo ciclo usa due gruppi separati:

- **5–10 pratiche di calibrazione**: regole, profilo e interfaccia possono essere corretti;
- **20–25 pratiche blind**: software, Practice Model, Rule Pack, profilo azienda e protocolli sono congelati.

Lo stesso fornitore/template/famiglia fortemente simile non deve essere usato per creare leakage tra calibrazione e blind set. Il toolkit blocca il freeze quando lo stesso `similarity_group` appare nei due gruppi.

## Freeze e ground truth

Prima del blind run viene creato un Pilot Manifest con commit/versione software, versioni e hash degli artefatti, preregistrazione e identificazione del dataset. Il Manifest viene a sua volta sigillato con timestamp e SHA-256.

La ground truth dei casi blind deve essere completata senza vedere l'output di ThisTinti. La modalità preferita usa due revisori indipendenti seguiti da adjudication; se esiste un solo revisore qualificato, il limite viene dichiarato esplicitamente e non viene simulata una doppia revisione.

Gli hash dei documenti aziendali riservati restano nell'inventario privato locale. Il rapporto pubblico non deve esporre inutilmente le impronte dei singoli file.

## Metriche

Il rapporto mostra prima i numeratori e denominatori e soltanto dopo le percentuali:

- true positive, false positive e false negative;
- critical miss;
- precision e recall con intervalli d'incertezza;
- risultati per tipologia di pratica;
- potenziale esposizione rilevata e mancata;
- perdita confermata e perdita evitata, quando realmente classificabili;
- eventuale disaccordo fra revisori.

Una discrepanza economica non equivale automaticamente a una perdita.

## Regola di change control

Durante il blind run non si correggono gli errori. Se è necessario modificare software, Rule Pack, Practice Model, Company Profile, protocollo o ground truth, quel run termina. Si crea un nuovo Manifest e i risultati restano separati.

Gli errori del blind run alimentano `results/blind-backlog.csv` per la versione successiva.

## Ruoli

L'azienda:

- sceglie i dati e ne garantisce autorizzazione e liceità;
- gestisce accessi, backup e sicurezza;
- fornisce o autorizza la ground truth professionale;
- verifica i risultati;
- decide se continuare a utilizzare o modificare il software.

Il progetto ThisTinti:

- fornisce software, protocollo, toolkit e test pubblici;
- non deve ricevere documenti aziendali non autorizzati;
- non autocertifica indipendenza dei revisori o materialità economica;
- non assume obblighi di assistenza, continuità o risultato tramite il software gratuito.

## Confine delle affermazioni

Con 20–25 pratiche blind è corretto dichiarare, per esempio:

> Nel pilot cieco Procurement v0.x, su 23 pratiche appartenenti al perimetro preregistrato…

Non è corretto trasformare quel risultato in una percentuale generale di accuratezza sull'intero procurement.

Non pubblicare nomi, importi, documenti, hash di file riservati o altre informazioni aziendali senza autorizzazione scritta.
