# Pre-pilot ThisTinti — flusso abbigliamento

## Perimetro scelto

Un solo processo: **ordine → consegna → fattura → reso → nota di credito**.

Il benchmark usa esclusivamente dati sintetici. Non contiene documenti aziendali reali e
non autorizza dichiarazioni commerciali di accuratezza.

## Trenta pratiche strutturate

- pratiche: **30**
- documenti: **100**
- anomalie attese: **26**
- precisione: **1.000**
- richiamo: **1.000**
- F1: **1.000**
- errore medio importi: **€ 0.00**
- falsi positivi: **0**
- falsi negativi: **0**
- gate tecnico superato: **SÌ**
- tempo motore complessivo: **1.097 s**
- tempo medio per pratica: **0.037 s**

## Scansioni sintetiche difficili

Questa prova separata usa tre PDF composti soltanto da immagini: una scansione pulita,
una a basso contrasto e una leggermente ruotata e rumorosa. È una diagnosi OCR, non una
misura di accuratezza su scansioni reali.

| Caso | Variante | Esito ingestione | Stato | Righe | Secondi |
|---|---|---|---|---:|---:|
| scan-01 | clear | parse_failed | failed | 0 | 1.075 |
| scan-02 | low-contrast | parse_failed | failed | 0 | 0.833 |
| scan-03 | rotated-noisy | parse_failed | failed | 0 | 1.869 |

## Misure non inventate

Il confronto **tempo umano prima/dopo** e il **giudizio degli utilizzatori** non sono
misurabili senza persone reali che eseguano lo stesso controllo. Per questo sono lasciati
esplicitamente aperti nel file CSV allegato invece di essere stimati o simulati.

## Conclusione corretta

Questo lavoro completa un **pre-pilot tecnico sintetico**. Il pilot reale richiede ancora:

1. almeno 30 pratiche aziendali autorizzate e, quando necessario, anonimizzate;
2. ground truth concordata da due revisori distinti;
3. tempi manuali e assistiti realmente cronometrati;
4. giudizio degli utilizzatori e registrazione dei falsi negativi conosciuti.
