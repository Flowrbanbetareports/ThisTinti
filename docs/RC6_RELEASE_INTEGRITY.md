# RC6 — evidenza di esecuzione Release Integrity

Questo documento registra fatti riproducibili relativi alla seconda PR RC6. Non è una dichiarazione di beta
validata e non sostituisce i log firmati dei workflow GitHub.

## Problemi riprodotti prima della modifica

1. `python scripts/verify_release.py --internal-checks` falliva con `OpenAPI metadata mismatch`: OpenAPI e SBOM
   versionati riportavano `3.4.0-alpha.5`, mentre applicazione, pacchetto Python e installer riportavano
   `3.4.0-alpha.7-rc.5`.
2. Dopo la rigenerazione, l'endpoint `GET /api/validation/runs/{run_id}/report` esponeva una risposta JSON senza
   schema OpenAPI.
3. Il gate completo rigenerava OpenAPI e SBOM prima di verificarli. Un clone con file obsoleti poteva quindi
   modificare silenziosamente il working tree durante il controllo.
4. `builds/release-latest.json` e `builds/publication-latest.json` indicavano ancora alpha.4, benché RC5 fosse
   pubblicata. Gli hash alpha.4 registrati non coincidevano più con gli asset attualmente osservabili nella release.
5. Il workflow speciale RC5 conteneva commit, artifact ID e checksum cablati. Accettava un artefatto prodotto da un
   commit PR diverso dal commit della release senza provare automaticamente l'identità del tree.
6. Lo smoke HTTP locale ereditava i proxy di sistema. Con un proxy SOCKS configurato e `socksio` non installato,
   `make verify` falliva prima di contattare `127.0.0.1`.
7. Il workflow Windows scaricava una baseline alpha.4 per nome, senza confrontarne l'hash prima dell'esecuzione.

## Evidenza storica RC5 verificata

Il 25 luglio 2026 sono stati interrogati gli endpoint REST pubblici GitHub e confrontato l'installer allegato:

- release RC5: `v3.4.0-alpha.7-rc.5`, ID `359442978`;
- commit release: `3ba42c8fd61043bd57d26fd04d937e7275818300`;
- artifact Windows: ID `8603465283`, workflow run `30110553366`, commit
  `9a1d172971dfc5e8af4e3dc79fff1b061d7160e4`;
- tree del commit artifact e del commit release:
  `e483e40131d43cf0db78dd2c04f33daab563267b`;
- SHA-256 installer pubblicato e allegato:
  `3df354de308fcc3d3aba5ea1a3ca85d05c147c9b41f6891f9499bcde458172e1`.

L'identità del tree RC5 è quindi un fatto verificato a posteriori. Il difetto era l'assenza di questa prova nel
workflow che autorizzava la pubblicazione.

## Modifiche

- modello Pydantic completo per il rapporto Validation Lab, con schema OpenAPI JSON e formato Markdown dichiarato;
- generatori OpenAPI/SBOM riproducibili anche su output temporaneo;
- controllo unico di versione, riferimenti SBOM, file generati, baseline Windows ed evidenza dell'ultima release;
- `make verify` read-only rispetto a OpenAPI/SBOM e obbligatorio nella CI Linux e come dipendenza della build Windows;
- baseline Windows RC5 versionata e verificata con SHA-256 prima dell'esecuzione;
- rapporto macchina del ciclo installazione → aggiornamento → smoke → disinstallazione → conservazione dati;
- inventario degli artefatti con commit, tree, dimensione e SHA-256;
- pubblicazione soltanto manuale, immutabile e subordinata a workflow verdi sullo stesso commit, attestazioni e
  nuova esecuzione di `make verify`;
- inclusione nell'artefatto di documenti legali, OpenAPI, SBOM e note di rilascio;
- correzione degli smoke locali affinché non usino proxy del sistema per `127.0.0.1`;
- evidenza RC5 `release-latest` e `publication-latest` aggiornata con dati osservati e hash riprodotti.

## Test eseguiti localmente

- test mirati Release Integrity, Validation Lab, legal e publication readiness: verdi;
- regressione dell'artefatto: un binario modificato dopo la creazione del manifesto viene rifiutato;
- regressione exact-commit: un workflow Windows riferito a un altro commit viene rifiutato;
- smoke HTTP reale con proxy SOCKS ereditato dall'ambiente: verde dopo la correzione;
- validazione sintattica di tutti i workflow YAML: verde;
- `make verify`: verde;
- copertura statement dopo l'integrazione della PR Data Integrity: `4835/5355` (`90,29%`), senza esclusioni o
  soglie ridotte;
- migrazioni SQLite upgrade/check/downgrade/upgrade: verdi;
- validation gate, HTTP smoke, backup, verifica backup e restore: verdi;
- `git diff --check`: verde.

## Aspetti non ancora dimostrati da questa evidenza locale

- esecuzione dei workflow GitHub della presente PR;
- compilazione e ciclo installazione della candidata su un runner Windows dopo queste modifiche;
- collaudo manuale su hardware Windows di Lorenzo;
- firma Authenticode, pentest, WCAG manuale e dataset aziendale autorizzato.

Nessuno di questi aspetti viene dichiarato superato finché non esiste la relativa evidenza.
