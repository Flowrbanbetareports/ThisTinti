# Staging esterna controllata

Questa configurazione serve a dimostrare ThisTinti fuori dall'ambiente locale senza presentarlo come produzione certificata.

## Requisiti

- host Linux con Docker Engine e Compose;
- DNS dedicato che punti all'host;
- porte 80 e 443 raggiungibili;
- nessun dato personale o aziendale non anonimizzato;
- backup del volume PostgreSQL prima di ogni aggiornamento.

## Avvio

1. Copiare `deploy/staging.env.example` in `.env.staging` e sostituire ogni placeholder.
2. Eseguire il preflight caricando le variabili del file.
3. Avviare `docker-compose.staging.yml` con il file ambiente.
4. Controllare i log di `db-roles`, `migrate`, `app`, `worker` e `proxy`.
5. Creare il primo amministratore con registrazione temporaneamente abilitata.
6. Portare `THISTINTI_ALLOW_REGISTRATION=false` e ricreare app e worker.
7. Eseguire `scripts/staging_acceptance.py` contro l'URL HTTPS.
8. Riavviare app e worker, ripetere l'accettazione senza bootstrap e verificare la persistenza.

## Evidenze richieste

Conservare il report JSON di accettazione, i log del deploy, la versione dell'immagine, l'hash del pacchetto sorgente, l'esito dello smoke PostgreSQL RLS e una prova di restore del backup.

## Limiti

Lo staging non sostituisce penetration test, scansione dipendenze online, test di carico o pilot con dataset reale anonimizzato. Lo scanner malware è facoltativo solo nello staging; deve essere obbligatorio prima di qualunque uso produttivo.

## Percorso gratuito consigliato

Per dimostrare il funzionamento fuori dal computer locale senza mantenere un server acceso, usare il job `postgres-external-proof` di GitHub Actions. Il job crea un PostgreSQL 16 effimero, configura ruoli separati senza `SUPERUSER` o `BYPASSRLS`, applica Alembic, verifica i guard multi-tenant, avvia API e worker, elabora un documento, riavvia entrambi i processi e verifica la persistenza di database, job, file e audit.

Il job non richiede credenziali Supabase, dati reali o servizi a pagamento. Le evidenze sono conservate per 14 giorni come artifact. Il progetto Supabase gratuito dedicato resta utile per prove database persistenti e non deve ricevere documenti sensibili durante il pilot tecnico.
