# RC13 — candidata interna di sicurezza

Versione: `3.4.0-alpha.7-rc.13`.

## Motivo

Il dependency audit online eseguito dopo la pubblicazione RC12 ha rilevato `PYSEC-2026-3655` e `PYSEC-2026-3656` su `pypdf` 6.14.2. Entrambi indicano 6.15.0 come versione corretta. Poiché ThisTinti analizza PDF non fidati, la dipendenza rientra nel perimetro reale di sicurezza e non viene ignorata o soppressa.

## Perimetro

- `pypdf` 6.14.2 → 6.15.0;
- lock Linux e development riallineate;
- SBOM e OpenAPI rigenerate con identità RC13;
- nessuna nuova funzione o modifica UI;
- nessun cambiamento a telemetria, cloud, account, pagamenti o automazioni economiche.

## Promozione

RC13 può essere pubblicata soltanto dopo CI completa, dependency audit verde, test PDF/parser, prove PostgreSQL/self-hosted, build e ciclo Windows sul commit esatto, checksum e provenienza. `3.4.0-alpha.7-rc.12` resta immutabile fino a quella pubblicazione separata.

I gate esterni di pilot reale, sicurezza indipendente, revisione legale/privacy/marchio, WCAG manuale, test con utenti non istruiti, infrastruttura definitiva e firma Authenticode restano aperti.
