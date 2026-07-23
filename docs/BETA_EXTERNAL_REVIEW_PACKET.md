# Pacchetto per le revisioni indipendenti della beta

## Identificazione del candidato

Ogni revisione deve indicare:

- versione applicativa e commit Git;
- hash SHA-256 degli artefatti esaminati;
- modalità Local Edition o Self-Hosted Reference Edition;
- configurazione, sistema operativo e database;
- data, perimetro, esclusioni e nominativo del revisore.

## Security review

Perimetro minimo:

- autenticazione, sessioni, CSRF, CORS e CSP;
- autorizzazioni e separazione dei tenant;
- ruoli PostgreSQL, RLS e migrazioni;
- upload, quarantena, malware scanning, OCR e parser;
- path traversal, decompression bomb, resource exhaustion e file ambigui;
- audit trail, integrità delle prove e log sensibili;
- segreti, dipendenze, workflow, SBOM e provenienza degli artefatti;
- backup, ripristino, aggiornamento e risposta agli incidenti;
- configurazione reverse proxy e TLS della Self-Hosted Reference Edition.

Il rapporto deve classificare gravità e riproducibilità, fornire evidenze e indicare il retest. Nessun rilievo critico o alto può restare aperto senza accettazione formale del rischio.

## Revisione legale e privacy

Perimetro minimo:

- licenza Apache 2.0, NOTICE e dipendenze;
- condizioni d'uso, disclaimer, supporto e dichiarazioni pubbliche;
- titolare/responsabile, basi giuridiche, DPA e subfornitori;
- minimizzazione, conservazione, cancellazione, accessi e data breach;
- flussi Local Edition e self-hosted;
- nome, dominio e marchi nelle classi e nei territori previsti;
- uso di documenti commerciali, dati personali e informazioni riservate nel pilot.

## Accessibilità

Usare `docs/ACCESSIBILITY_CONFORMANCE_PLAN.md`. Il controllo automatico deve essere affiancato da tastiera, zoom, contrasto e tecnologie assistive.

## Pilot e accuratezza

Usare `docs/PILOT_DATASET_SPEC.md`, `docs/PILOT_KIT.md` e `docs/VALIDATION_PROTOCOL.md`. Il revisore della ground truth non deve derivare le risposte dal risultato prodotto da ThisTinti.

## Consegna delle evidenze

Nel repository pubblico si registrano soltanto stato, data, versione, ambito, hash del rapporto e riferimento a una copia custodita in modo appropriato. Non pubblicare vulnerabilità non corrette, chiavi, documenti aziendali, dati personali o dettagli riservati.
