# Public Evidence Benchmark 30 — risultato

Generated: `2026-08-26T21:51:17.682841+00:00`  
Engine: `3.4.0-alpha.7-rc.13`

## Evidenza

Questo è un benchmark indipendente, non un pilot aziendale reale. I 10 casi pubblici sono rappresentazioni normalizzate di record Portland; i 10 casi mutati sono derivati controllati; gli ultimi 10 sono sintetici professionali. La ground truth è separata dall'input e viene usata solo dall'evaluator dopo l'ingestione.

## Metriche

- scenari: **30**
- documenti: **103**
- anomalie attese: **17**
- TP / FP / FN: **17 / 0 / 0**
- precisione: **1.000**
- recall: **1.000**
- F1: **1.000**
- MAE importi: **0.00**
- gate: **PASS**
- tempo: **1.161 s**

| Categoria | Scenari | TP | FP | FN | Precisione | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| public_record_baseline | 10 | 0 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| public_record_mutation | 10 | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| synthetic_full_chain | 10 | 7 | 0 | 0 | 1.000 | 1.000 | 1.000 |

## Integrità

- SHA-256 input: `5ef5805d2c7da0a0de8ad1cee07e700bffbda462e24c23b3c1123609c7fcff1a`
- SHA-256 ground truth: `eabbbdec535777d18b39754b1394be31f778daad344544131aec918abc95589c`
- ground truth separata: **sì**
- pilot reale completato: **no**
