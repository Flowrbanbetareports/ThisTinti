# Public Evidence Benchmark 30

## Scopo

Questo benchmark mette ThisTinti alla prova con un livello di evidenza più forte del pre-pilot interamente sintetico, senza confonderlo con un pilot aziendale reale.

La versione 1.0 contiene esattamente:

- **10 public-record baseline**: record realmente pubblicati dalla City of Portland, trasformati soltanto in una rappresentazione JSON minima compatibile con ThisTinti. Non vengono inventati fatture, pagamenti, fornitori o importi non presenti nella fonte;
- **10 public-record mutation**: dagli stessi dieci record viene costruita una catena controllata ordine → consegna → fattura e viene introdotta una sola mutazione dichiarata e congelata prima dell'esecuzione;
- **10 synthetic full-chain**: catene professionali con proposta, ordine, conferma, consegna, fattura e pagamento; alcuni casi aggiungono reso e nota di credito.

Totale: **30 scenari**.

## Perché resta `synthetic`

Il pacchetto è deliberatamente classificato `evidence_level: synthetic`. I record Portland sono reali, ma sono normalizzati; i casi mutati contengono documenti derivati e le catene complete finali sono sintetiche. Questo benchmark non deve quindi soddisfare né aggirare il gate `anonymized_pilot` previsto per almeno 30 pratiche aziendali autorizzate.

Il pilot reale resta separato e richiede autorizzazione, due revisori, ground truth indipendente e documenti reali secondo `docs/PILOT_DATASET_SPEC.md`.

## Ground truth separata

Il builder produce due file distinti. Il dataset contiene gli input destinati al motore e mantiene `expected: []` in tutti i 30 scenari. Il file ground truth contiene categoria, provenienza, mutazione e risultato atteso.

Il runner inserisce gli attesi soltanto nella fase di confronto del Validation Lab. Il codice di ingestione riceve i documenti prima che il comparatore usi la ground truth. In questo modo l'elenco delle anomalie attese non guida il motore durante parsing, matching o generazione delle segnalazioni.

Le metriche prodotte sono veri positivi, falsi positivi, falsi negativi, precisione, recall, F1, errore assoluto medio sull'importo, risultati per categoria e tempo di esecuzione. Vengono registrati anche gli SHA-256 di dataset e ground truth.

## Fonte primaria: City of Portland OCDS

- pubblicazione ufficiale: `https://www.portland.gov/business-opportunities/ocds/ocds-data-publication`
- policy e mappatura: `https://www.portland.gov/business-opportunities/ocds/pdx-ocds-publication-policy`
- explorer usato per congelare i dieci record: `https://portland-ocds.wegov.nyc/`

La City of Portland descrive la propria pubblicazione OCDS come derivata dai sistemi BuySpeed, SAP e B2G e resa disponibile in formati aperti. La stessa policy avverte che persistono problemi di qualità: per questo ogni caso conserva OCID e fatti sorgente, così la normalizzazione resta verificabile.

I dieci OCID v1 sono:

1. `ocds-ptecst-133262`
2. `ocds-ptecst-133299`
3. `ocds-ptecst-133238`
4. `ocds-ptecst-132893`
5. `ocds-ptecst-132928`
6. `ocds-ptecst-132925`
7. `ocds-ptecst-132815`
8. `ocds-ptecst-133038`
9. `ocds-ptecst-133001`
10. `ocds-ptecst-132953`

I fatti congelati sono in `samples/public_evidence_benchmark_30_sources.json`.

## Fonti successive già individuate

La pubblicazione COTAI nel registro Open Contracting è una seconda fonte concreta: il registro espone 104 contratti, 567 transazioni e 603 documenti e segnala problemi di qualità propri. Non viene inserita nella v1 finché non vengono congelati singoli record con la stessa tracciabilità applicata a Portland.

Gli esempi Peppol BIS Billing / EN 16931 saranno usati per l'estensione XML. Sono materiali ufficiali di interoperabilità ma non transazioni aziendali realmente avvenute, quindi non saranno mai etichettati come `public_record_baseline`.

## Mutazioni controllate

La v1 esercita quattro famiglie già supportate dal motore:

- `price_over_order`;
- `invoiced_over_received`;
- `discount_missing`;
- `unmatched_invoice_line`.

Ogni scenario `public_record_mutation` ha una sola mutazione dichiarata nella ground truth con valore baseline e valore mutato. Gli importi attesi vengono congelati prima dell'esecuzione.

Le dieci catene sintetiche estendono inoltre la copertura con `return_without_credit` e `credit_below_return`.

## Gate

Il benchmark richiede almeno:

- precisione ≥ 0,95;
- recall ≥ 0,95;
- F1 ≥ 0,95;
- MAE importi ≤ 0,05.

Il workflow fallisce se il gate non è superato. Un fallimento non viene nascosto: diventa evidenza di una debolezza del motore da correggere e trasformare in regressione.

## Esecuzione

```bash
python scripts/build_public_evidence_benchmark.py \
  --dataset builds/public-evidence-benchmark-30-dataset.json \
  --ground-truth builds/public-evidence-benchmark-30-ground-truth.json

python scripts/run_public_evidence_benchmark.py \
  builds/public-evidence-benchmark-30-dataset.json \
  builds/public-evidence-benchmark-30-ground-truth.json \
  --report builds/public-evidence-benchmark-30-latest.json \
  --markdown builds/public-evidence-benchmark-30-latest.md
```

Il workflow dedicato è `.github/workflows/public-evidence-benchmark-30.yml`.

## Limiti

Un PASS non significa pilot reale completato. Restano fuori: 30 flussi aziendali completi realmente avvenuti, OCR su scansioni reali eterogenee, tempi umani prima/dopo, usabilità con personale non istruito e validazione professionale legale/fiscale/contabile.
