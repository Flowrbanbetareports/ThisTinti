# RC6 execution log

Questo registro distingue risultati eseguiti nel repository da prove che richiedono
ancora CI o un host Windows reale. Non sostituisce release note o attestazioni.

## Data Integrity

| Voce | Stato |
| --- | --- |
| Fase | Implementata; PR draft aperta, CI remota in corso |
| Branch e PR | `codex/rc6-data-integrity`, [PR #43](https://github.com/Flowrbanbetareports/ThisTinti/pull/43) |
| Commit remoto | `7f3bfeb3fb40ebfe8ec129ad019cbc4d01690fed` |
| Base verificata | `428289beafdbd9fcf5bf3253d57373a5cd9fc4ff` |
| Problema | Numeri invalidi/non finiti convertiti in zero; forme JSON non validate; campi mancanti esposti come zero |
| Causa | Helper numerico permissivo, parser senza contratto di forma e database RC5 con colonne numeriche non nullable |
| Correzione | Parsing decimale stretto, errori strutturati, provenienza numerica, 422 persistente e guardie nei confronti |
| Riproduzione precedente | 30 fallimenti nei nuovi test mirati sulla base RC5 |
| Test successivi | 220 test; `make check`; copertura applicativa 90,18% (4764/5283 statement) |
| Formati coperti | JSON, CSV, XLSX, FatturaPA XML, UBL, P7M delegato a XML, PDF controllato |
| Rischi residui | CI Linux/Windows non ancora eseguita sul commit remoto; nessun installer ricostruito in questa fase |
| Prossimo intervento | Release Integrity: metadati, OpenAPI, SBOM e gate CI/Windows |

## Evidenze da non dichiarare ancora

- Nessun test Windows installato, aggiornamento o disinstallazione è stato eseguito
  da questo ambiente.
- Nessun artefatto RC6 è stato pubblicato.
- Nessun pentest, firma Authenticode o collaudo con corpus aziendale reale è incluso
  nei risultati interni.
