# Adaptive Discovery — ThisTinti 3.2.0-alpha.1

## Obiettivo

Adaptive Discovery osserva i documenti del tenant, costruisce un profilo operativo e propone controlli coerenti con i dati presenti, senza richiedere una scelta iniziale rigida del settore.

## Flusso

1. conta tipi di documento, campi e valori ricorrenti;
2. analizza descrizioni, codici, varianti e campi non standard;
3. suggerisce un'attività probabile con confidenza ed evidenze;
4. propone regole sostenute dai dati osservati;
5. auto-attiva soltanto controlli **predefiniti e deterministici** sufficientemente supportati;
6. assegna sempre alle regole scoperte dinamicamente lo stato `needs_confirmation`, anche sopra soglia;
7. non applica ipotesi troppo deboli;
8. conserva conferme, correzioni, rifiuti e richieste di riapprendimento;
9. rianalizza le catene dopo una decisione.

## Regole dinamiche

Campi ricorrenti non previsti, come matricola, scadenza, peso, periodo di servizio o tracking, possono produrre una proposta di controllo di coerenza. Ogni proposta conserva copertura, tipi documentali, esempi, confidenza, motivazione e decisione umana.

Una proposta dinamica non diventa automaticamente una regola applicata. Il revisore deve confermarla; il rifiuto viene conservato e prevale sui cicli successivi, salvo riapprendimento esplicito.

## Profilo attività

Il profilo può essere:

- confermato;
- corretto specificando tipo ed etichetta;
- rimesso in apprendimento.

Il profilo serve a migliorare priorità e suggerimenti, non a concedere permessi o a decidere azioni economiche.

## Limiti di sicurezza

Adaptive Discovery non modifica pagamenti, contabilità, anagrafiche esterne o comunicazioni. Una confidenza elevata non equivale a certezza. Le regole apprese richiedono sempre una decisione umana e restano isolate per tenant e registrate nell'audit.
