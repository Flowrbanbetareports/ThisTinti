# Revisione preliminare delle licenze

## Perimetro

La revisione automatica usa:

- `requirements*.txt` e file lock;
- `docs/sbom.cdx.json`;
- licenza Apache 2.0 del progetto;
- componenti inclusi nelle build Windows e self-hosted.

Non sostituisce un parere legale sulle licenze.

## Stato preliminare

L'inventario generato dall'ambiente esatto è disponibile in
`docs/licenses-inventory.csv`. Le dipendenze sono in prevalenza MIT, BSD, Apache, PSF,
ISC o equivalenti. Sono presenti anche componenti con obblighi specifici:

- `psycopg` e `psycopg-binary`: LGPL-3.0;
- `certifi`: MPL-2.0;
- `pypdfium2`/PDFium: licenze BSD, Apache e licenze delle dipendenze incorporate.

Queste licenze non rendono automaticamente incompatibile la distribuzione, ma richiedono
conservazione degli avvisi e verifica della modalità concreta di bundling. Non è stato
intenzionalmente inserito codice applicativo AGPL o SSPL.

## Componenti che richiedono avvisi specifici

- Python e libreria standard: conservare gli avvisi PSF applicabili.
- Tesseract OCR e `tessdata_fast`: conservare licenza e notice Apache-2.0.
- `pypdfium2`/PDFium: conservare le licenze BSD/Apache e quelle delle dipendenze
  incorporate indicate dal progetto upstream.
- Inno Setup: è uno strumento di build; verificare e rispettare le sue condizioni nella
  pipeline di rilascio.
- Icone, font e immagini: distribuire soltanto asset creati per il progetto o con licenza
  documentata.
- Documenti di esempio: usare soltanto dati sintetici o anonimizzati con autorizzazione.

## Gate obbligatorio per ogni release

1. Rigenerare l'SBOM e `docs/licenses-inventory.csv` nell'ambiente di build esatto.
2. Eseguire l'audit delle dipendenze con accesso Internet.
3. Estrarre le licenze dai pacchetti realmente inclusi nell'installer.
4. Bloccare componenti con licenza sconosciuta o incompatibile.
5. Allegare `LICENSE`, `NOTICE`, `docs/THIRD_PARTY_NOTICES.md` e SBOM.
6. Verificare che il sorgente pubblicato corrisponda esattamente ai binari.

## Limite della revisione attuale

La verifica completa dell'installer può avvenire soltanto dopo la build Windows su
GitHub Actions. Fino ad allora il controllo sui componenti congelati è preparatorio.
