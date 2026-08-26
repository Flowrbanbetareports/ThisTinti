# RC13 — hotfix di sicurezza e promozione a Public Preview

Versione: `3.4.0-alpha.7-rc.13`.

Stato finale: **pubblicata come Public Preview prerelease** il `2026-08-26T20:17:41Z`.

## Motivo

Il dependency audit online eseguito dopo la pubblicazione RC12 ha rilevato `PYSEC-2026-3655` e `PYSEC-2026-3656` su `pypdf` 6.14.2. Entrambi indicavano 6.15.0 come versione corretta. Poiché ThisTinti analizza PDF non fidati, la dipendenza rientra nel perimetro reale di sicurezza e non è stata ignorata o soppressa.

## Perimetro

- `pypdf` 6.14.2 → 6.15.0;
- lock Linux e development riallineate;
- SBOM e OpenAPI rigenerate con identità RC13;
- versione applicativa e installer allineati a RC13;
- nessuna nuova funzione o modifica UI;
- nessun cambiamento a telemetria, cloud, account, pagamenti o automazioni economiche.

## Evidenza preliminare

Prima del cambio di identità a RC13, la sostituzione isolata della dipendenza è stata eseguita nel draft PR #100 sul commit `2a4e16f6c9e9e2c54ceb77907088b25740c6ece7`: il dependency audit è tornato verde e i check associati a quel commit si sono conclusi senza failure. Questa prova ha giustificato la preparazione della candidata, senza sostituire i gate sulla sorgente RC13 finale.

## Evidenza della candidata finale

La PR #100 è stata completata dopo il riallineamento dell’asserzione di versione rimasta a RC12 nei test. Il commit candidato finale del ramo è stato `edd10ee6b95562c847540715a812ff198ae03e6f`.

Dopo i gate del ramo, la PR è stata unita in `main` producendo il commit applicativo di rilascio:

- commit: `f7609b51aec4c358d0410ca8ff83e60485cac96c`;
- tree: `e1a5ea29d4bbef7e1431d96fa5a5149dc4a46e3c`.

Sul commit esatto sono stati rieseguiti i gate applicabili, inclusi dependency audit, compatibilità Python, PostgreSQL, prove self-hosted e ciclo Windows.

## Evidenza Windows

- workflow: `Build Windows Free Download`;
- run ID: `33008478384`;
- build/run number: `394`;
- artifact: `ThisTinti-Windows-33008478384-394`;
- installer: `ThisTinti-Setup-3.4.0-alpha.7-rc.13-x64.exe`;
- SHA-256 installer: `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`;
- portable SHA-256: `92dafd018bd27c4a088c1977fcaf3e1713f03ccb83feed2540c0a60481ebeea2`;
- self-hosted source SHA-256: `e4025e7bf9cdadc8696ea6fa365de212a7b701fa4062116e3f4c355c16863d7d`.

Il manifest di provenienza registra come superati checksum, identità portable, smoke congelato, smoke installato, Diagnostica installata e lifecycle installer.

## Pubblicazione

La richiesta di pubblicazione ha vincolato esplicitamente la release al commit applicativo `f7609b51aec4c358d0410ca8ff83e60485cac96c` e al Windows run `33008478384`.

Il workflow di pubblicazione ha rieseguito il gate completo sull’esatta sorgente, richiesto workflow verdi, scaricato l’artefatto Windows esatto, verificato checksum, smoke report, provenienza e attestazioni e applicato il controllo contro sostituzione/riuso scorretto della release.

Risultato:

- tag: `v3.4.0-alpha.7-rc.13`;
- release ID: `377397969`;
- titolo: `ThisTinti 3.4.0-alpha.7-rc.13 — Public Preview`;
- prerelease: sì;
- draft: no;
- asset pubblicati: 23;
- URL: https://github.com/Flowrbanbetareports/ThisTinti/releases/tag/v3.4.0-alpha.7-rc.13;
- evidenza registrata in `builds/publication-latest.json`.

La RC12 resta immutabile come release storica; non è stata sovrascritta. RC13 è la Public Preview corrente.

## Gate deliberatamente ancora aperti

La promozione a Public Preview non equivale a beta validata o produzione. Restano da documentare con evidenza reale:

- collaudo umano end-to-end della RC13;
- pilot reale su almeno 30 scenari autorizzati con ground truth e metriche;
- sessioni con utenti non istruiti;
- penetration test indipendente e retest;
- revisione professionale legale/privacy/marchio;
- collaudo WCAG 2.2 AA manuale con tecnologie assistive;
- prove sull’infrastruttura definitiva;
- firma Authenticode e timestamp;
- accettazione formale dei rischi residui.

Questo documento resta nel repository come registro storico della motivazione, verifica e promozione dell’hotfix RC13.
