# Brief per una revisione di sicurezza indipendente

## Perimetro minimo

- autenticazione, sessioni, CSRF e ruoli;
- isolamento tenant e RLS PostgreSQL;
- upload, parser PDF/XML/XLSX/P7M e OCR;
- path traversal, decompression bomb e file ostili;
- worker, code persistenti e race condition;
- backup, restore e cancellazione;
- Docker, proxy, TLS, segreti, ClamAV e reti;
- installer Windows e meccanismo di aggiornamento;
- dipendenze e supply chain GitHub Actions.

## Materiale da fornire

- commit e tag esatti;
- SBOM e file lock;
- threat model;
- documentazione dell'architettura;
- ambiente di test isolato senza dati reali;
- elenco delle limitazioni note.

## Output richiesto

- gravità e riproducibilità dei rilievi;
- prova tecnica essenziale;
- remediation consigliata;
- distinzione tra difetti del progetto e configurazioni dell'operatore;
- retest dopo le correzioni.

Non inviare vulnerabilità con dati reali o credenziali tramite issue pubbliche.
