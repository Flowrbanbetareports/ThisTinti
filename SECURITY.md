# Sicurezza di ThisTinti

## Controlli implementati

### Identità e sessioni

- password PBKDF2-SHA256 con 310.000 iterazioni e salt casuale;
- sessioni HMAC con scadenza;
- cookie `HttpOnly`, `SameSite=Strict` e opzione `Secure`;
- token CSRF separato e confronto constant-time;
- controllo `Origin` sulle richieste non sicure del browser;
- revoca delle sessioni tramite incremento di `token_version`;
- utente disattivato escluso immediatamente;
- protezione dell'ultimo amministratore attivo;
- ruoli admin/reviewer/viewer applicati agli endpoint.

### Separazione dei dati

- ogni entità operativa contiene `tenant_id`;
- ogni query protetta filtra per tenant;
- vincoli e chiavi esterne limitano associazioni incoerenti;
- test automatici verificano l'isolamento tra organizzazioni.

### File e parser

- whitelist delle estensioni;
- limite dimensione configurabile;
- rifiuto dei file vuoti;
- nomi sanitizzati e percorsi non controllabili dall'utente;
- hash SHA-256 e deduplicazione;
- validazione firma PDF/XLSX;
- protezione contro XLSX/ZIP anomali;
- XML con DTD ed entità esterne rifiutato;
- nessuna esecuzione dei file caricati;
- OCR eseguito senza shell, con timeout, pagine/DPI/output limitati e directory temporanea;
- testo OCR marcato come dato derivato e non equivalente alla fonte strutturata;
- P7M verificato per integrità della firma senza dichiarare fidata la catena del certificato;
- rielaborazione atomica e preservazione dei dati precedenti in caso di errore.

### Applicazione web

- Content Security Policy restrittiva;
- `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- Permissions Policy restrittiva;
- rate limiting locale per login, registrazione e upload;
- risposte API non memorizzate in cache;
- token non salvati in `localStorage` o `sessionStorage`.

### Integrità e operazioni

- importi gestiti con `Decimal`/`Numeric`;
- audit con catena hash per tenant;
- endpoint di verifica dell'audit;
- export amministrativo temporaneo con cancellazione dopo il download;
- readiness check su database, storage, segreto e impostazioni produzione;
- applicazione Docker eseguita come utente non root, filesystem read-only e capability rimosse.

## Segreti

Non inserire mai password, chiavi API o credenziali nel repository. La chiave OpenAI precedentemente esposta non è inclusa né utilizzata da ThisTinti.

Generare il segreto applicativo con:

```bash
python scripts/generate_secret.py
```

## Controlli obbligatori prima di Internet pubblico

- HTTPS end-to-end e `THISTINTI_SECURE_COOKIES=true`;
- proxy fidato con limiti upload e timeout;
- rate limiting distribuito, non solo in memoria;
- scanner malware/antivirus degli allegati;
- object storage privato e cifrato;
- backup cifrati e restore provato;
- gestione centralizzata dei log e alert;
- rotazione dei segreti;
- politica di conservazione/cancellazione;
- penetration test indipendente;
- audit delle dipendenze con accesso Internet;
- piano di risposta agli incidenti.

## Segnalazione vulnerabilità

Non aprire pubblicamente un issue contenente dati sensibili o exploit completi. Usare un canale privato definito dal gestore dell'installazione.

## Self-Hosted Reference Edition

La configurazione `deploy/enterprise` aggiunge separazione di rete, segreti basati su file, registrazione pubblica disabilitata, bootstrap offline del primo amministratore, PostgreSQL, worker scalabili, ClamAV e reverse proxy HTTPS.

Questi controlli non costituiscono certificazione né trasferiscono la gestione all’autore. L’operatore deve verificare immagini, sistema host, firewall, TLS, firme malware, backup, monitoring, capacity, accessi e incident response. Il file locale `operator-acceptance.json` deve corrispondere alla versione e agli hash dei documenti legali; una modifica richiede nuova presa visione.
