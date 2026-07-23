# Prestazioni, capacità e obiettivi di servizio

## Scopo

La prova automatica inclusa nel repository serve a rilevare regressioni evidenti. Non dimensiona un ambiente aziendale e non sostituisce un test sull'infrastruttura definitiva.

## Baseline tecnica del candidato beta

Il workflow `Beta Readiness` esegue richieste concorrenti a endpoint non distruttivi e registra:

- richieste totali e completate;
- error rate;
- latenza minima, media, p50, p95 e p99;
- throughput osservato;
- versione e commit del codice.

Gate predefinito del smoke load test:

- nessun errore HTTP o di trasporto;
- p95 non superiore a 750 ms sul runner CI;
- almeno 200 richieste con concorrenza 20.

Questi valori sono deliberatamente conservativi e hanno valore di regressione, non di promessa contrattuale.

## Test obbligatorio sull'ambiente definitivo

Prima di una beta validata l'organizzazione deve definire:

- utenti concorrenti e volume giornaliero;
- dimensioni e tipologie dei documenti;
- RPO e RTO;
- disponibilità attesa e finestre di manutenzione;
- capacità di storage e conservazione;
- limiti di CPU, memoria, database, worker e scanner;
- comportamento durante picchi, riavvii, indisponibilità del database e code arretrate.

La prova deve includere durata, concorrenza, ingestione di file rappresentativi, backup contemporaneo, ripristino, crescita del database e osservabilità. I risultati vanno associati al commit e alla configurazione esatti.

## Nessuno SLA implicito

Il software gratuito e self-hosted non include SLA. Eventuali SLO o SLA devono essere definiti dall'organizzazione o da un fornitore contrattualmente separato.
