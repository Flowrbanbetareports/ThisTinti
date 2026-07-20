# ThisTinti Self-Hosted Reference Edition

## Che cos’è

È una configurazione gratuita e modificabile per organizzazioni che vogliono eseguire ThisTinti nella propria infrastruttura. Include PostgreSQL, più worker, reverse proxy HTTPS, scanner malware, backup e strumenti operativi.

Non è un servizio gestito dall’autore e non è una certificazione di idoneità produttiva per qualunque azienda. L’organizzazione deve farla valutare, installare e mantenere da personale qualificato.

## Componenti inclusi

- applicazione FastAPI e interfaccia web;
- PostgreSQL con ruoli separati e protezioni multi-tenant;
- worker persistenti e scalabili;
- ClamAV separato, raggiunto tramite protocollo `INSTREAM`;
- Caddy come reverse proxy HTTPS;
- segreti Docker basati su file locali;
- inizializzazione fail-closed e prova di presa visione locale;
- bootstrap offline del primo amministratore, senza aprire la registrazione pubblica;
- backup PostgreSQL + storage e ripristino esplicito;
- reti Docker separate: solo il proxy espone porte pubbliche.

## Requisiti minimi consigliati per un pilot

- host Linux aggiornato;
- Docker Engine e Docker Compose recenti;
- DNS controllato dall’organizzazione;
- 4 vCPU, 8 GB RAM e spazio disco adeguato ai documenti;
- backup esterno al server;
- personale tecnico in grado di gestire Docker, PostgreSQL, TLS e sicurezza.

Questi valori non sono una garanzia di capacità. I requisiti reali dipendono da volume, OCR, dimensione dei file e concorrenza.

## Inizializzazione

Dalla radice del repository:

```bash
python scripts/enterprise_init.py \
  --host thistinti.example.com \
  --accept-operator-responsibility \
  --accept-no-support

python scripts/enterprise_preflight.py --directory deploy/enterprise
```

Lo script genera segreti distinti, `.env` e `operator-acceptance.json`. Tutti restano locali e sono esclusi da Git.

## Avvio

```bash
cd deploy/enterprise
docker compose -f docker-compose.enterprise.yml --profile ops run --rm preflight
docker compose -f docker-compose.enterprise.yml up -d --build
```

ClamAV può impiegare alcuni minuti al primo avvio per predisporre le firme. Finché scanner e worker non risultano operativi, `/api/readiness` deve restituire 503 e il proxy non deve considerare pronta l’applicazione.

## Primo amministratore

La registrazione pubblica è sempre disabilitata. Creare il primo amministratore da terminale:

```bash
read -s ADMIN_PASSWORD
printf '%s\n' "$ADMIN_PASSWORD" | docker compose -f docker-compose.enterprise.yml \
  --profile ops run --rm admin-bootstrap \
  python scripts/enterprise_create_admin.py \
  --organization "Azienda Demo" \
  --email admin@example.com \
  --password-stdin
unset ADMIN_PASSWORD
```

Il bootstrap si rifiuta di procedere se esiste già almeno un utente.

## Scalare i worker

Il file `.env` imposta il numero di repliche. È possibile anche usare:

```bash
docker compose -f docker-compose.enterprise.yml up -d --scale worker=4
```

Aumentare i worker non sostituisce test di carico, monitoraggio del database e dimensionamento OCR.

## Backup

Creare un backup con nome esplicito:

```bash
BACKUP="/backups/thistinti-$(date -u +%Y%m%dT%H%M%SZ).zip"
docker compose -f docker-compose.enterprise.yml --profile ops run --rm backup \
  python scripts/backup_system.py "$BACKUP"
```

Il file contiene dump PostgreSQL, storage, manifest e SHA-256. Copiarlo poi su un sistema separato e provarne periodicamente il ripristino.

## Ripristino

Arrestare prima app e worker. Eseguire il ripristino solo su un ambiente controllato e con una copia dei dati correnti:

```bash
docker compose -f docker-compose.enterprise.yml stop app worker proxy

docker compose -f docker-compose.enterprise.yml --profile ops run --rm restore \
  python scripts/restore_backup.py /backups/NOME.zip \
  --postgres-url-file /run/secrets/database_owner_url \
  --storage-dir /app/data/uploads \
  --confirm-restore --force
```

Il comando sopra è un riferimento operativo: l’organizzazione deve verificare percorsi, permessi e procedura sul proprio ambiente prima dell’uso reale.

## Aggiornamento

1. verificare note di rilascio e migrazioni;
2. creare e verificare un backup;
3. provare l’aggiornamento in staging;
4. fermare il traffico;
5. ricostruire le immagini;
6. eseguire la migrazione una sola volta;
7. controllare readiness, login, documenti campione, audit e worker;
8. conservare il piano di rollback.

## Cosa resta a carico dell’azienda

Vedere `docs/RESPONSIBILITY_MATRIX.md`. In particolare: infrastruttura, privacy, sicurezza, accessi, costi, backup, monitoraggio, integrazioni, aggiornamenti, incidenti e decisioni basate sugli output.
