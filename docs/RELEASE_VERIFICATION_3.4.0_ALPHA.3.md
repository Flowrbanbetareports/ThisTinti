# ThisTinti 3.4.0-alpha.3 — verifica del rebranding

## Esito

Il rebranding tecnico è concluso e i controlli locali previsti sono stati superati.

- nome applicato: `ThisTinti` / `THISTINTI` / `thistinti` secondo il contesto;
- occorrenze residue del nome precedente nei file e percorsi distribuiti: 0;
- test raccolti e superati: 155;
- copertura applicativa combinata: 90%;
- Ruff, formattazione, Bandit, compilazione Python e sintassi JavaScript: superati;
- migrazioni SQLite: upgrade, downgrade completo e nuovo upgrade superati;
- Validation Gate sintetico: precisione, recall e F1 pari a 1, MAE importi pari a 0;
- smoke HTTP: superato;
- Local Edition: elaborazione, arresto, riavvio e persistenza superati;
- dipendenze dichiarate: 63 distribuzioni validate;
- inventario licenze: 70 distribuzioni;
- OpenAPI e SBOM: rigenerati per `3.4.0-alpha.3`.

## Ambito della modifica

Sono stati aggiornati pacchetto Python, eseguibile, installer, cookie, variabili d'ambiente,
database locale, configurazioni Docker/PostgreSQL, sito, testi legali, documentazione, esempi,
workflow, OpenAPI, SBOM e pacchetti di rilascio.

## Compatibilità

Le versioni antecedenti erano alpha non pubblicate. Non viene mantenuta compatibilità con nomi di
variabili, cookie o directory delle build di prova. L'AppId Windows resta stabile per consentire
l'aggiornamento delle installazioni sperimentali già presenti.

## Stato del nome

La ricerca pubblica esatta è favorevole e non ha rilevato utilizzi identici. Restano manuali:

1. verifica live dei domini immediatamente prima dell'acquisto;
2. ricerca diretta in TMview/EUIPO, UIBM e WIPO sui segni simili;
3. eventuale parere professionale prima di registrare o promuovere il marchio su larga scala.

Questi limiti non impediscono l'uso del nome nelle release alpha, ma impediscono di dichiararlo
registrato, esclusivo o giuridicamente garantito.
