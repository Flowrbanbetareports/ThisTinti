# Pre-pilot ThisTinti su 30 pratiche

## Fase 1 — processo scelto

Il perimetro è intenzionalmente unico e vicino all'esperienza operativa del promotore:

**ordine → consegna → fattura → reso → nota di credito** nel settore abbigliamento.

Il processo comprende soltanto il controllo di coerenza fra documenti della stessa pratica. Non comprende pagamenti, contabilità generale, contestazioni automatiche o decisioni economiche autonome.

## Fase 2 — trenta pratiche sintetiche

Il dataset `samples/pilot_apparel_30_synthetic.json` contiene 30 scenari indipendenti e 100 documenti strutturati:

- 6 catene completamente coerenti;
- 2 ordini con consegne e fatture multiple;
- 5 quantità fatturate superiori alla consegna;
- 4 prezzi superiori all'ordine;
- 4 sconti ordinati ma assenti in fattura;
- 3 righe fattura non presenti nei documenti precedenti;
- 2 resi senza nota di credito;
- 2 note di credito parziali;
- 2 pratiche con codici articolo differenti ma descrizione, colore e taglia compatibili.

Una prova OCR separata genera inoltre tre PDF composti soltanto da immagini: pulito, a basso contrasto e ruotato con rumore. Il runner assegna esplicitamente il tipo `invoice`, richiesto dal percorso di ingestione PDF. Questa parte misura il comportamento tecnico del parser, non l'accuratezza su scansioni aziendali reali.

Tutti i nomi, numeri e valori sono artificiali. Il dataset è classificato `synthetic`, non contiene autorizzazioni aziendali e non può essere approvato per automazioni.

## Fase 3 — misure prodotte automaticamente

Il comando seguente produce un rapporto JSON, un riepilogo Markdown e un foglio CSV per la misurazione umana:

```bash
python scripts/run_apparel_pilot.py \
  samples/pilot_apparel_30_synthetic.json \
  --report builds/apparel-pre-pilot-30-latest.json \
  --markdown builds/apparel-pre-pilot-30-latest.md \
  --measurement-template builds/apparel-real-pilot-measurements.csv
```

Le misure tecniche comprendono:

- veri positivi, falsi positivi e falsi negativi;
- precisione, richiamo e F1;
- errore medio sugli importi;
- esito di ogni scenario;
- tempo complessivo del motore e tempo medio per pratica;
- esito delle tre scansioni sintetiche.

## Cosa non viene simulato

Il tempo umano prima e dopo ThisTinti e il giudizio degli utilizzatori restano vuoti finché non vengono osservati realmente. Il file CSV generato contiene una riga per ciascuna pratica e i campi per:

- due revisori distinti;
- tempo manuale senza ThisTinti;
- tempo di verifica con ThisTinti;
- anomalia reale e anomalia segnalata;
- falso positivo e falso negativo;
- giudizio dell'utilizzatore da 1 a 5;
- note.

Inventare tali valori trasformerebbe un pre-pilot tecnico in una falsa evidenza commerciale.

## Confine del risultato

Il completamento di questo lavoro dimostra che il prodotto può essere sottoposto a un benchmark riproducibile di 30 pratiche su un processo definito. Non dimostra ancora utilità o accuratezza in un'azienda reale.

Per chiudere il pilot reale servono ancora documenti autorizzati e, quando necessario, anonimizzati; due revisori indipendenti; tempi cronometrati; e giudizi di utilizzatori effettivi. Il protocollo completo resta in `docs/VALIDATION_PROTOCOL.md`.
