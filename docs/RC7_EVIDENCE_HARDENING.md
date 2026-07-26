# RC7 evidence hardening

## Base verificata

La riproduzione parte dal Portable pubblico RC6 con SHA-256
`81562015e8f351f9e99ab38ee16a4f42d1af96b0d249cf436b9f9c283ad25f80`.
Il file coincide per dimensione e hash con l'asset registrato per il build Windows 200
del commit `0c86e669bbbecadcada3581dfd842a2f7fd9c3b5`.

## Problemi riprodotti nel sorgente RC6

1. Il dettaglio documento non espone `archived` e `file_available`.
2. Un percorso di storage che non è un file supera il controllo `exists()` e può
   arrivare a `FileResponse`.
3. L'errore di apertura dell'originale viene mostrato soltanto in un toast temporaneo.
4. Le righe delle anomalie sono cliccabili ma non attivabili da tastiera.
5. La severità `critical` ha badge e ordinamento, ma non uno stile dedicato della riga
   né un conteggio persistente nella pagina Anomalie.
6. Il test Chromium RC6 delle evidenze usa risposte API simulate; i test API e browser
   coprono due metà del flusso, non l'interazione completa con storage reale.

## Comportamento atteso

- un file mancante o un percorso non-file restituisce `410` senza perdere il record e
  le righe estratte;
- archivio e disponibilità del file sono dichiarati nel dettaglio documento;
- errori di file mancante, documento non autorizzato e permessi insufficienti restano
  visibili nel dialogo;
- `critical` è contata, filtrabile, ordinata e visivamente distinguibile;
- `Invio` e `Spazio` aprono una riga anomalia focalizzata;
- il browser test verifica stato archiviato, file mancante, errore persistente e tastiera.

## Evidenze richieste prima del merge

- test API mirati di `tests/test_evidence_workflow.py`;
- `scripts/check_evidence_browser.py` con Chromium reale;
- `node --check app/static/app-core.js`;
- OpenAPI riproducibile;
- `make verify`;
- CI completa, gate Simplified Product Experience e build Windows verdi sul commit
  esatto della PR.

## Limiti

I test automatici non stabiliscono conformità WCAG e non sostituiscono un collaudo
manuale con tecnologie assistive. Nessun risultato viene considerato chiuso finché il
workflow remoto non ha eseguito i test del codice effettivamente proposto.
