# Pilot reale ThisTinti — settore abbigliamento

## Obiettivo

Misurare, su un solo processo autorizzato, se ThisTinti riduce il tempo di controllo senza introdurre errori silenziosi.

Il processo resta:

**ordine → consegna → fattura → reso → nota di credito**

Non sono incluse azioni esterne automatiche, pagamenti, scritture contabili, contestazioni ai fornitori o decisioni economiche autonome.

## 1. Requisiti minimi

Il pilot parte solo quando sono disponibili:

- autorizzazione scritta dell'organizzazione titolare dei documenti;
- almeno 30 pratiche indipendenti;
- documenti anonimizzati oppure ambiente locale formalmente autorizzato;
- due revisori distinti;
- un utilizzatore che esegua il controllo manuale e quello assistito;
- versione di ThisTinti registrata nel rapporto;
- nessuna sincronizzazione cloud non autorizzata.

## 2. Preparazione dell'area di lavoro

```bash
python scripts/real_pilot_toolkit.py prepare ./real-pilot-apparel \
  --pilot-id APPAREL-PILOT-001 \
  --organization-alias ORG-001 \
  --case-count 30
```

Il comando crea:

- `pilot-manifest.json`;
- `AUTHORIZATION.md`;
- `measurements.csv`;
- 30 cartelle separate in `input/CASE-001` … `input/CASE-030`.

Ogni pratica deve contenere esclusivamente i documenti che la riguardano. Non mescolare fornitori o processi differenti nella stessa cartella.

## 3. Autorizzazione e anonimizzazione

Prima del caricamento:

1. compilare e firmare `AUTHORIZATION.md`;
2. impostare `authorization.status` a `approved` nel manifest;
3. rimuovere nomi di persone, email, telefoni, IBAN, codici fiscali e altri identificativi non necessari;
4. sostituire ragioni sociali e riferimenti con alias stabili;
5. mantenere una tabella di corrispondenza fuori dal workspace del pilot;
6. verificare manualmente immagini e PDF scannerizzati.

Eseguire quindi:

```bash
python scripts/real_pilot_toolkit.py inspect ./real-pilot-apparel
```

Il controllo automatico cerca identificativi nei file testuali, inventaria ogni file e segnala i documenti binari che richiedono revisione manuale.

## 4. Ground truth

I revisori `REV-A` e `REV-B` lavorano indipendentemente e registrano per ogni pratica:

- documenti correttamente collegati;
- anomalie effettive;
- importo dell'anomalia;
- gravità;
- casi non determinabili.

Le divergenze devono essere risolte prima di confrontare il risultato con ThisTinti. La ground truth non può essere costruita dopo aver visto le segnalazioni del software.

## 5. Misurazione prima/dopo

Per ogni pratica eseguire due sessioni separate:

### Controllo manuale

- cronometrare dall'apertura del primo documento alla decisione finale;
- registrare anomalie individuate;
- evitare l'uso di ThisTinti;
- registrare il tempo in `manual_seconds`.

### Controllo assistito

- caricare la stessa pratica in ThisTinti;
- cronometrare caricamento, revisione e decisione finale;
- verificare sempre i documenti originali;
- registrare il tempo in `assisted_seconds`;
- registrare segnalazioni corrette, falsi positivi, falsi negativi e voto dell'utilizzatore.

Per ridurre l'effetto memoria, alternare l'ordine delle sessioni tra le pratiche oppure separarle temporalmente.

## 6. Campi obbligatori

Il file `measurements.csv` richiede:

- due revisori distinti;
- ground truth completata;
- tempo manuale e assistito maggiori di zero;
- numero di anomalie reali e segnalate;
- falsi positivi e falsi negativi;
- indicazione di eventuali errori critici non rilevati;
- giudizio dell'utilizzatore da 1 a 5;
- note operative.

## 7. Rapporto finale

```bash
python scripts/real_pilot_toolkit.py summarize ./real-pilot-apparel
```

Il comando produce:

- `result.json`, utilizzabile come evidenza strutturata;
- `result.md`, leggibile da persone non tecniche.

La decisione automatica può essere:

- `incompleto`;
- `non_idoneo`;
- `idoneo_solo_con_revisione_rafforzata`;
- `idoneo_con_revisione_umana`.

Nessuno di questi esiti costituisce certificazione legale, contabile o di sicurezza.

## 8. Criteri di interruzione immediata

Il pilot viene sospeso quando si verifica uno dei seguenti eventi:

- documento non autorizzato;
- presenza di dati personali non necessari;
- contaminazione tra pratiche o organizzazioni;
- collegamento errato silenzioso;
- errore critico non rilevato;
- impossibilità di ricostruire l'origine di una segnalazione;
- richiesta di azioni esterne automatiche.

## 9. Conservazione e chiusura

Alla fine del pilot:

- esportare rapporto, manifest, inventario e misurazioni;
- conservare soltanto per il periodo autorizzato;
- eliminare copie temporanee e cartelle di prova;
- documentare data e responsabile della cancellazione;
- mantenere `safe_to_automate=false` salvo approvazione separata sul run esatto.
