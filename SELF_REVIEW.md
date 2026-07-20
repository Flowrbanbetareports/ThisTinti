# Riesame critico di ThisTinti

## “Supporta qualunque documento”

Falso. XML FatturaPA/UBL e dati tabellari conformi restano il percorso più affidabile. L’OCR locale amplia la copertura delle scansioni, ma non rende affidabile qualunque layout: i valori sono marcati come derivati e il sistema richiede revisione quando la tabella non è riconoscibile.

## “Il matching automatico è perfetto”

Falso. Il matching per riferimento è forte; quello per similarità è volutamente prudente. I documenti incerti restano scollegati e possono essere associati manualmente.

## “Un'applicazione completa è automaticamente pronta per ogni azienda”

Falso. Il prodotto è completo nel perimetro tecnico definito, ma la validità economica richiede documenti reali, misurazione degli errori e integrazioni specifiche.

## Riesame architetturale

La prima impostazione uno-a-uno tra catena e documenti era insufficiente. È stata sostituita da `chain_documents`, che supporta più DDT, più fatture, più resi e più note di credito. Un vincolo impedisce allo stesso documento di appartenere a due catene.

## Riesame monetario

L'uso di `float` sarebbe stato inaccettabile per confronti economici. Quantità e importi sono stati convertiti a `Decimal`/`Numeric` con scale esplicite.

## Riesame audit

Un normale registro modificabile non era sufficiente. Ogni evento include ora l'hash dell'evento precedente e il proprio hash; l'endpoint di verifica rileva modifiche retroattive.

## Riesame sessioni

Il salvataggio del bearer token nel browser avrebbe ampliato il rischio XSS. Il frontend usa ora cookie HttpOnly e protezione CSRF. Il bearer token resta disponibile solo in modalità API esplicita.

## Riesame rielaborazione

La rielaborazione non deve cancellare dati validi prima di sapere se il nuovo parsing funziona. Il processo è atomico: in caso di errore conserva le righe precedenti e registra l'evento.

## Rischi residui reali

- OCR e layout PDF non standard, soprattutto tabelle senza separatori chiari;
- corrispondenze tra codici articolo molto differenti;
- regole contrattuali specifiche non rappresentate nei documenti;
- rate limiting in memoria non adatto a più istanze;
- assenza di scansione malware integrata;
- PostgreSQL e Docker non eseguiti in questo ambiente, pur avendo migrazioni e configurazioni predisposte;
- assenza di pilot su dati aziendali reali;
- assenza di penetration test indipendente.

## Criterio corretto per dichiarare affidabilità

Un pilot deve produrre almeno:

- precisione dei casi segnalati;
- richiamo rispetto alle anomalie note;
- tasso di documenti non interpretabili;
- tempo medio risparmiato;
- valore economico confermato;
- numero di correzioni manuali richieste.

Senza queste metriche è scorretto dichiarare che il sistema “recupera denaro” o che non perde anomalie.
