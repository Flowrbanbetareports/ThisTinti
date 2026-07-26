# Grafo delle evidenze e controlli euristici

I nomi storici di alcuni endpoint e campi restano disponibili per compatibilità. Non descrivono un certificatore, un digital twin, un sistema antifrode o un motore autorizzato a prendere decisioni economiche.

## Obiettivo

ThisTinti costruisce una rappresentazione verificabile dell'operazione documentale e prepara informazioni per quattro domande:

1. che cosa sembra essere successo;
2. quali evidenze hanno generato il risultato;
3. che cosa manca o potrebbe accadere dopo;
4. quali segnali richiedono verifica prima di applicare le procedure dell'organizzazione.

## Grafo delle evidenze

Ogni proposta, ordine, conferma, consegna, fattura, pagamento, reso e nota di credito diventa un nodo. Gli archi descrivono riferimenti espliciti, collegamenti ricostruiti e relazioni economiche. Ogni nodo e collegamento espone confidenza, stato e motivazione.

Il grafo non sostituisce il file originale. È un indice spiegabile delle evidenze usate dal motore.

## Documenti attesi e scadenze indicative

Il controllo genera documenti attesi e relative scadenze indicative. All'inizio usa tempi prudenziali predefiniti. Dopo almeno tre osservazioni compatibili per lo stesso fornitore può usare il percentile 80 dello storico privato dell'azienda. Lo storico non viene condiviso con altri tenant.

Questa euristica non dimostra che un documento manchi davvero. Indica una prova mancante, scaduta o ancora attesa che una persona deve verificare.

## Stima euristica prima della revisione

Gli endpoint storicamente denominati di simulazione stimano segnali interni relativi ad azioni ipotetiche, come la revisione di una fattura o di un pagamento. Non eseguono né autorizzano l'azione. Il risultato contiene:

- punteggio e livello euristico;
- stato tecnico interno (`allow`, `review`, `block`), mostrato in interfaccia come segnale basso, verifica richiesta o verifica prioritaria;
- importo potenzialmente esposto;
- motivazioni;
- contratto delle prove;
- incertezza e stato della calibrazione.

`safe_to_automate` resta falso finché il rischio non è basso e non esiste un run reale esplicitamente approvato. Sono richiesti: evidenza `anonymized_pilot` o `production`, almeno 30 scenari, versione del motore corrente e approvazione amministrativa registrata nell'audit. La suite sintetica non può sbloccare automazioni. Una nuova esecuzione del dataset revoca l'idoneità precedente fino a nuova revisione. La stima non esegue l'azione reale.

La stima `amount_at_risk` evita di sommare più volte lo stesso importo quando diverse anomalie descrivono la medesima esposizione. Un'ipotesi senza il relativo documento viene rifiutata come incoerente; non viene bloccata alcuna operazione esterna.

## Controllo incrociato di tre segnali

La preview confronta tre fonti interne:

1. estrazione del documento;
2. coerenza aritmetica ed economica;
3. compatibilità logica con il grafo delle evidenze.

Non è ancora attivo un secondo modello multimodale esterno. L'architettura è predisposta per aggiungerlo come fonte separata, ma la preview non dichiara una lettura AI indipendente che non è stata installata.

## Somiglianza al processo osservato

Il sistema ricava le varianti di processo più frequenti del tenant e del fornitore e confronta la pratica corrente con il percorso dominante. È una misura di somiglianza, non una verifica formale di conformità. I passaggi generici facoltativi non vengono trattati come obbligatori; la prova di consegna per beni fisici è valutata separatamente dal Sentinel.

## Scenari sintetici di errore

L'endpoint storico `red-team` verifica sette famiglie di errore senza mutare i documenti. La copertura è calcolata sugli scenari applicabili alla pratica; quelli non applicabili vengono separati dai mancati rilevamenti:

- quantità o importi alterati;
- documento mancante;
- pagamento doppio;
- pagamento senza fattura;
- riferimento cross-tenant;
- collegamento fornitore incoerente;
- sequenza di processo anomala.

Il risultato misura copertura e scenari rilevati. È un controllo regressivo sintetico, non un penetration test, un red-team indipendente o una prova antifrode.

## Pattern anonimi

L'export anonimo contiene solo varianti di processo aggregate, famiglie di regole e frequenze raggruppate. Non include documenti, nomi, identificativi, date, importi, testo grezzo o pattern rari sotto la soglia minima. È una base per un eventuale apprendimento condiviso; non costituisce ancora federated learning crittografico.

## Limiti della preview

- necessita di pilot e calibrazione su documenti reali anonimizzati; la soglia tecnica minima di 30 scenari non sostituisce il campione consigliato di almeno 100 catene;
- la lettura delle scansioni difficili resta dipendente da OCR e revisione umana;
- non esegue azioni su ERP, banca o contabilità;
- non sostituisce revisione fiscale, legale o contabile;
- scenari sintetici e pattern anonimi devono essere valutati su casi del settore;
- nessun risultato probabilistico viene trattato come prova certa senza evidenze sufficienti.
