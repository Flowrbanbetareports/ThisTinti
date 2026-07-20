# Rebranding ThisTinti 3.4.0-alpha.3

## Scopo

Il progetto è stato rinominato integralmente prima del lancio pubblico. La modifica riguarda il nome
visibile e tutti gli identificatori tecnici controllati dal progetto.

## Elementi aggiornati

- nome del pacchetto Python;
- eseguibile, installer, icona e cartelle locali;
- cookie, variabili d'ambiente, nomi database ed esempi di dominio;
- Docker Compose, PostgreSQL, RLS e configurazioni di staging;
- documentazione, sito statico, testi legali e guide operative;
- OpenAPI, SBOM, pacchetti ZIP, bundle Git e workflow di release;
- test e controlli automatici di pubblicazione.

## Compatibilità

Le versioni antecedenti erano alpha non pubblicate. Non viene quindi mantenuta una compatibilità
pubblica con variabili, cookie o directory locali precedenti. L'AppId Windows resta stabile per
consentire l'aggiornamento delle installazioni di prova eventualmente già create.

## Protezione dalle regressioni

La release include un controllo che fallisce se un file o un percorso tracciato contiene ancora il
nome precedente. Le sole eccezioni ammissibili sarebbero evidenze esterne storiche non distribuite;
nessuna eccezione è attualmente necessaria nel repository.
