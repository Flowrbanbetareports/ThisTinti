# ThisTinti 3.4.0-alpha.1 — verifica Enterprise Self-Hosted Reference

Data: 20 luglio 2026

## Scopo

Questa edizione è una configurazione tecnica gratuita e open source che un'organizzazione o il proprio fornitore può installare e gestire sulla propria infrastruttura. Non è hosting, consulenza, certificazione, assistenza, manutenzione o servizio gestito dall'autore.

## Capacità incluse

- PostgreSQL con ruoli separati per amministrazione, migrazioni e runtime.
- Applicazione e worker multipli in container separati.
- Reverse proxy HTTPS di riferimento con Caddy.
- Scanner malware ClamAV obbligatorio e fail-closed.
- Registrazione pubblica disabilitata e creazione offline del primo amministratore.
- Segreti tramite file locali esclusi dal pacchetto e dal controllo versione.
- Backup e ripristino di database e storage.
- Preflight che blocca configurazioni incomplete o accettazioni legali obsolete.
- Workflow GitHub per la prova completa del deployment Docker.

## Verifiche concluse

- 151 test superati, 0 fallimenti.
- Copertura applicativa del 90% nel gate combinato della versione 3.4.
- Ruff, formattazione, Bandit, compilazione Python e sintassi JavaScript puliti.
- 15 test mirati enterprise, scanner, backup e configurazione production superati.
- Migrazioni avanti, indietro e nuovamente avanti superate.
- Validation Gate sintetico, smoke HTTP e prova locale con riavvio/persistenza superati.
- File Compose validi a livello strutturale YAML.
- Pacchetto controllato per escludere `.env`, accettazioni, segreti, backup e log dell'operatore.

## Verifiche che richiedono GitHub

Docker non è disponibile nell'ambiente in cui è stata preparata la release. Il workflow `enterprise-self-hosted.yml` è quindi pronto ma non ancora eseguito. Prima di rimuovere l'etichetta alpha deve dimostrare sul runner Linux: build, PostgreSQL, ClamAV, migrazioni, bootstrap amministratore, autenticazione, elaborazione, backup, riavvio e persistenza.

Anche l'installazione esatta delle dipendenze bloccate e `pip-audit` restano gate della CI.

## Confine delle responsabilità

L'organizzazione che installa o fa modificare il software resta responsabile della propria infrastruttura, dei dati, della sicurezza, degli accessi, della privacy, dei backup, degli aggiornamenti, dei costi, degli incidenti, delle integrazioni e della verifica umana dei risultati. L'accettazione resta sul sistema dell'operatore e non viene trasmessa all'autore.

Queste misure riducono l'ambiguità operativa, ma non promettono immunità assoluta da responsabilità né possono escludere obblighi inderogabili di legge.
