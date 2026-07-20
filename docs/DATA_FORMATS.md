# Formati dati supportati

## Principio generale

ThisTinti conserva sempre il file originale e separa:

1. dati letti direttamente;
2. dati normalizzati;
3. regole di confronto;
4. conclusione proposta.

Un campo mancante non viene inventato. I documenti non interpretabili ricevono stato di parsing fallito o incompleto.

## Tipi documento

Valori ammessi:

- `proposal`
- `order`
- `confirmation`
- `delivery`
- `invoice`
- `payment`
- `return`
- `credit_note`

## JSON strutturato

Esempio minimo:

```json
{
  "document_type": "order",
  "number": "PO-1001",
  "document_date": "2026-07-19",
  "currency": "EUR",
  "supplier": {
    "name": "Fornitore Demo",
    "vat_id": "IT00000000000"
  },
  "references": ["PO-1001"],
  "lines": [
    {
      "line_no": 1,
      "sku": "ART-145",
      "description": "Giacca blu taglia 48",
      "color": "blu",
      "size": "48",
      "lot": "SS26",
      "quantity": 10,
      "unit_price": 42.00,
      "discount_rate": 8,
      "tax_rate": 22,
      "line_total": 386.40
    }
  ]
}
```

I file completi di esempio sono in `samples/`.

## CSV

Intestazioni riconosciute, con varianti comuni:

- `line_no`
- `sku`, `code`, `item_code`
- `description`, `item`, `product`
- `color`, `colour`
- `size`
- `lot`, `batch`, `season`
- `quantity`, `qty`
- `unit_price`, `price`
- `discount_rate`, `discount`
- `tax_rate`, `vat`
- `line_total`, `total`

Il file deve contenere almeno SKU o descrizione e una quantità valida. Il tipo documento, il numero e il fornitore possono essere indicati nel form di caricamento.

## XLSX/XLSM

Usa la prima tabella utile del primo foglio. Le intestazioni sono normalizzate come nel CSV. Le formule non vengono eseguite: viene letto il valore salvato nel file.

Il parser limita dimensioni compresse, numero di elementi e rapporto di espansione per ridurre il rischio di ZIP bomb.

## FatturaPA XML

Sono letti, quando presenti:

- cedente/prestatore;
- partita IVA;
- numero e data documento;
- valuta;
- tipo documento;
- righe, quantità, prezzo unitario, sconto, aliquota e totale;
- riferimenti a ordini e DDT.

I documenti con DTD o entità esterne vengono rifiutati.

## PDF testuale controllato

Il PDF deve avere testo estraibile. Le righe prodotto devono essere separate da `;`, `|` oppure tab, con una struttura coerente, per esempio:

```text
ART-145 ; Giacca blu ; blu ; 48 ; 10 ; 42.00 ; 8 ; 386.40
```


## Numeri

- separatore decimale `.` o `,` nei formati tabellari;
- valori non finiti (`NaN`, `Infinity`) rifiutati;
- importi salvati con precisione decimale;
- quantità con massimo quattro decimali;
- prezzi unitari con massimo sei decimali;
- totali con massimo due decimali.

## Duplicati

Lo stesso contenuto caricato due volte nello stesso tenant viene riconosciuto tramite SHA-256. Il file non viene duplicato e viene restituito il documento già esistente.

## P7M

Sono accettate fatture FatturaPA XML racchiuse in una busta CMS/PKCS#7 DER con estensione `.p7m`. ThisTinti:

1. verifica l'integrità crittografica della firma;
2. estrae il contenuto allegato;
3. accetta solo contenuto XML riconoscibile;
4. applica le protezioni DTD/XXE del parser XML.

La verifica non controlla attendibilità, scadenza o revoca della catena del certificato. Questa distinzione viene registrata nei metadati.

## ZIP batch

Un archivio `.zip` può contenere fino a 200 file supportati. Non sono accettati membri cifrati. Percorsi assoluti o con `..` vengono rifiutati. Gli archivi con dimensione espansa o rapporto di compressione anomali vengono bloccati.


## UBL/Peppol

Sono riconosciuti i root UBL `Invoice`, `CreditNote`, `Order`, `OrderResponse`, `DespatchAdvice` e `ReceiptAdvice`. ThisTinti legge identificativo, data, valuta, fornitore, riferimenti e righe commerciali. I profili specifici vanno comunque validati sul campione aziendale.

## PDF e OCR

Il parser tenta prima il testo incorporato. Se il PDF è una scansione e OCR è abilitato, Poppler renderizza un numero limitato di pagine e Tesseract estrae il testo localmente. La tabella automatica richiede righe nel formato:

```text
SKU ; Descrizione ; Quantità ; Prezzo ; Sconto ; Colore ; Taglia
```

Metadati e righe provenienti da OCR riportano `extraction_method=local_ocr` e una confidenza inferiore. Nessun servizio esterno riceve i documenti.

Per un documento classificato come `payment`, ThisTinti può riconoscere prudenzialmente un importo indicato come `IMPORTO`, `TOTALE`, `PAGATO` o accompagnato da EUR/€. L'importo diventa una singola riga economica con evidenza `receipt_total`. Se deriva da OCR la revisione umana resta raccomandata.
