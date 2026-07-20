# Proof Graph & Sentinel — preview 3.2

## Obiettivo

ThisTinti 3.2 non si limita a leggere documenti o a trovare errori già avvenuti. Costruisce una rappresentazione verificabile dell'operazione commerciale e prova a rispondere a quattro domande:

1. che cosa è successo;
2. quali prove lo dimostrano;
3. che cosa manca o dovrebbe accadere dopo;
4. quale rischio si crea approvando un'azione adesso.

## Proof Graph

Ogni proposta, ordine, conferma, consegna, fattura, pagamento, reso e nota di credito diventa un nodo. Gli archi descrivono riferimenti espliciti, collegamenti ricostruiti e relazioni economiche. Ogni nodo e collegamento espone confidenza, stato e motivazione.

Il grafo non sostituisce il file originale. È un indice spiegabile delle evidenze usate dal motore.

## Sentinel Twin

Sentinel genera documenti attesi e relative scadenze. All'inizio usa tempi prudenziali predefiniti. Dopo almeno tre osservazioni compatibili per lo stesso fornitore può usare il percentile 80 dello storico privato dell'azienda. Lo storico non viene condiviso con altri tenant.

Una previsione non crea automaticamente un'anomalia contabile: indica una prova mancante, scaduta o ancora attesa.

## Simulazione preventiva

Gli endpoint di simulazione valutano azioni come approvare una fattura o un pagamento. Il risultato contiene:

- punteggio e livello di rischio;
- decisione proposta (`allow`, `review`, `block`);
- importo potenzialmente esposto;
- motivazioni;
- contratto delle prove;
- incertezza e stato della calibrazione.

`safe_to_automate` resta falso finché il rischio non è basso e non esiste un run reale esplicitamente approvato. Sono richiesti: evidenza `anonymized_pilot` o `production`, almeno 30 scenari, versione del motore corrente e approvazione amministrativa registrata nell'audit. La suite sintetica non può sbloccare automazioni. Una nuova esecuzione del dataset revoca l'idoneità precedente fino a nuova revisione. La simulazione non esegue l'azione reale.

La stima `amount_at_risk` evita di sommare più volte lo stesso importo quando diverse anomalie descrivono la medesima esposizione. Un'azione senza il relativo documento — per esempio approvare una fattura inesistente — viene bloccata.

## Tripla verifica

La preview confronta tre fonti interne:

1. estrazione del documento;
2. coerenza aritmetica ed economica;
3. compatibilità logica con il Proof Graph.

Non è ancora attivo un secondo modello multimodale esterno. L'architettura è predisposta per aggiungerlo come fonte separata, ma la preview non dichiara una lettura AI indipendente che non è stata installata.

## Process conformance

Il sistema apprende le varianti di processo più frequenti del tenant e del fornitore e confronta la pratica corrente con il percorso dominante. I passaggi generici facoltativi non vengono trattati come obbligatori; la prova di consegna per beni fisici è valutata separatamente dal Sentinel.

## Self-red-team

Il motore verifica sette famiglie di errore senza mutare i documenti. La copertura è calcolata sugli scenari applicabili alla pratica; quelli non applicabili vengono separati dai mancati rilevamenti:

- quantità o importi alterati;
- documento mancante;
- pagamento doppio;
- pagamento senza fattura;
- riferimento cross-tenant;
- collegamento fornitore incoerente;
- sequenza di processo anomala.

Il risultato misura copertura e scenari rilevati. È un controllo regressivo, non un penetration test.

## Pattern anonimi

L'export anonimo contiene solo varianti di processo aggregate, famiglie di regole e frequenze raggruppate. Non include documenti, nomi, identificativi, date, importi, testo grezzo o pattern rari sotto la soglia minima. È una base per un futuro apprendimento condiviso; non costituisce ancora federated learning crittografico.

## Limiti della preview

- necessita di pilot e calibrazione su documenti reali anonimizzati; la soglia tecnica minima di 30 scenari non sostituisce il campione consigliato di almeno 100 catene;
- la lettura delle scansioni difficili resta dipendente da OCR e revisione umana;
- non esegue azioni su ERP, banca o contabilità;
- non sostituisce revisione fiscale, legale o contabile;
- self-red-team e pattern anonimi devono essere valutati su casi del settore;
- nessun risultato probabilistico viene trattato come prova certa senza evidenze sufficienti.
