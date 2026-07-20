# Checklist prima dell’uso aziendale

La Self-Hosted Reference Edition non deve essere considerata pronta per la produzione finché l’organizzazione non ha completato e documentato almeno questi punti.

## Governance

- nominato un proprietario tecnico interno;
- identificati titolare/responsabili privacy e fornitori;
- approvati scopo, limiti e casi d’uso vietati;
- definito il controllo umano obbligatorio;
- predisposta una procedura alternativa senza ThisTinti.

## Infrastruttura

- host supportato e aggiornato;
- DNS e TLS verificati;
- porte pubbliche limitate al reverse proxy;
- database e storage non esposti;
- segreti fuori dal repository e con permessi ristretti;
- registrazione pubblica disabilitata;
- scanner malware e firme verificati;
- monitoraggio di readiness, worker, spazio, errori e certificati.

## Dati

- dataset di pilot anonimizzato o autorizzato;
- regole di conservazione e cancellazione;
- backup separato e cifrato quando necessario;
- restore provato su ambiente isolato;
- accessi minimi e revisione periodica degli utenti.

## Qualità e sicurezza

- test su documenti reali rappresentativi;
- misurati falsi positivi e falsi negativi;
- test di carico sull’infrastruttura finale;
- scansione vulnerabilità di immagini e dipendenze;
- penetration test indipendente prima dell’esposizione Internet;
- piano di patching e risposta agli incidenti.

## Accettazione

- `enterprise_preflight.py` verde;
- `/api/readiness` verde con almeno un worker;
- audit verificato;
- prova completa upload → worker → risultato → riavvio;
- approvazione formale del responsabile tecnico e del responsabile di processo.
