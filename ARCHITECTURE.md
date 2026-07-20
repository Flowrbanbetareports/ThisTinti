# Architettura di ThisTinti

## Obiettivo

ThisTinti trasforma documenti commerciali eterogenei in una catena verificabile e produce anomalie supportate da evidenze. Il sistema privilegia regole deterministiche e fallimenti espliciti.

## Flusso applicativo

1. **Ingestione** — file temporaneo, limiti, validazione, SHA-256, deduplicazione e storage privato.
2. **Parsing** — parser selezionato per formato; nessun campo inventato.
3. **Normalizzazione** — codici e descrizioni trasformati in chiavi canoniche.
4. **Matching documentale** — riferimenti espliciti, poi similarità prudente; alternativa manuale.
5. **Catena** — più documenti per ogni ruolo tramite `chain_documents`.
6. **Regole** — confronto deterministico di quantità, prezzi, sconti, valuta, resi e crediti.
7. **Evidence** — documento, riga, campo, osservato, atteso e nota.
8. **Review** — conferma, rifiuto, richiesta verifica o chiusura.
9. **Audit** — evento hash-chain per tenant.
10. **Export** — snapshot amministrativo JSON/CSV e file opzionali.

## Componenti

### Frontend

- HTML/CSS/JavaScript statici;
- autenticazione con cookie HttpOnly;
- CSRF cookie-to-header;
- viste dashboard, documenti, catene, casi, audit e utenti;
- controllo UI per ruolo, senza affidarsi alla UI per l'autorizzazione.

### API

- FastAPI;
- schemi Pydantic;
- autorizzazione server-side;
- errori HTTP espliciti;
- OpenAPI in `docs/openapi.json`.

### Persistenza

- SQLAlchemy 2;
- SQLite per uso locale;
- PostgreSQL per deployment;
- migrazioni Alembic;
- colonne `Numeric` per importi e quantità;
- chiavi esterne e check constraint.

### File

- storage locale nel rilascio autosufficiente;
- percorso derivato internamente;
- file originale immutabile;
- hash SHA-256;
- object storage privato consigliato per più istanze.

## Modello dati sintetico

```text
Tenant
 ├── User
 ├── Supplier
 ├── Document ── DocumentLine
 ├── OperationChain ── ChainDocument ── Document
 │    └── DiscrepancyCase ── EvidenceLink
 │         └── ReviewDecision
 └── AuditEvent
```

## Autenticazione e autorizzazione

- una nuova registrazione crea tenant e admin;
- password PBKDF2;
- sessione firmata con scadenza e `token_version`;
- browser: cookie HttpOnly + CSRF;
- integrazione API: bearer token solo con modalità esplicita;
- admin: gestione utenti/export/archiviazione/audit;
- reviewer: upload, collegamento, analisi e decisione;
- viewer: sola lettura.

## Coerenza

- un documento può appartenere a una sola catena;
- una catena può contenere più documenti dello stesso ruolo;
- la rielaborazione è atomica;
- ogni modifica rilevante produce audit;
- l'audit è concatenato con hash;
- un'analisi rigenera in modo idempotente i casi aperti derivati dalle regole.

## Scalabilità

La build è pronta per un'unica istanza o per una prima installazione PostgreSQL. Per scala orizzontale servono:

- object storage condiviso;
- rate limiting condiviso;
- coda job per parsing pesante;
- lock/distribuzione dei job;
- log e metriche centralizzati;
- reverse proxy e bilanciamento.

## Confini

- nessun OCR;
- nessun invio automatico al fornitore;
- nessuna scrittura contabile;
- nessuna API AI a pagamento;
- nessun accesso diretto al database dal browser.

## Validation Lab

`ValidationDataset` conserva una suite immutabile per nome/versione. `ValidationRun` registra motore, scenari, TP/FP/FN, precisione, recall, F1, errore medio sugli importi e risultato del gate.

Ogni scenario viene eseguito dentro un savepoint e un tenant tecnico temporaneo. I documenti e i file di prova vengono eliminati al termine; solo le metriche restano nel tenant proprietario della suite. In questo modo i benchmark non contaminano i dati operativi.

```text
Tenant
 ├── ValidationDataset
 │    └── ValidationRun
 ├── ItemAlias
 └── ...dati operativi
```

Il gate incorporato è eseguito anche dalla CI. Una suite sintetica impedisce regressioni note; una suite con documenti reali anonimizzati è necessaria per misurare l'idoneità operativa.

## Matching riga-per-riga

Il matching usa, in ordine:

1. chiave canonica esatta;
2. alias confermato per tenant e fornitore;
3. compatibilità obbligatoria di colore, taglia e lotto;
4. similarità SKU/descrizione con evidenza numerica prudente;
5. mancato collegamento esplicito sotto soglia.

Le corrispondenze fuzzy non vengono applicate tra righe dello stesso documento. Una conferma alias produce audit e rianalisi delle catene coinvolte.

## Ingestione firmata e massiva

- `.p7m`: OpenSSL verifica la firma CMS e ne estrae il contenuto; la catena di fiducia del certificato non viene certificata.
- `.zip`: massimo 200 membri, limite di espansione, rifiuto dei percorsi non sicuri e isolamento transazionale per membro.


### OCR locale

Per i PDF senza testo, un adattatore isolato usa `pdftoppm` e Tesseract senza shell. Il processo è limitato per pagine, DPI, tempo e caratteri prodotti. Il risultato conserva la provenienza `local_ocr` e la classe di evidenza `derived`; le regole non devono confonderlo con XML o dati tabellari strutturati.

### Interoperabilità UBL

Il dispatcher XML distingue FatturaPA dai principali documenti UBL/Peppol tramite il root element e normalizza entrambi nello stesso modello documentale interno.
