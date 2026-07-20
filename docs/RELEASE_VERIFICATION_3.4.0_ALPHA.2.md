# ThisTinti 3.4.0-alpha.2 — preparazione al lancio pubblico

Data: 20 luglio 2026.

## Esito tecnico

- 153 test raccolti e superati nell'ambiente con dipendenze esatte.
- Ruff, formattazione, Bandit, compilazione Python e sintassi JavaScript superati.
- Migrazioni SQLite: upgrade, check, downgrade completo e nuovo upgrade superati.
- Validation Gate sintetico: precisione, recall e F1 pari a 1; MAE importi pari a 0.
- Smoke HTTP: readiness e audit validi.
- Grafo dipendenze: 63 distribuzioni installate validate contro i requisiti.
- OpenAPI e SBOM rigenerati per la versione 3.4.0-alpha.2.
- Inventario licenze generato su 70 distribuzioni dell'ambiente di verifica.
- Gate di preparazione alla pubblicazione superato.

## Copertura

La logica applicativa non è stata modificata rispetto alla 3.4.0-alpha.1, salvo il
numero di versione. Il gate precedente aveva misurato il 90% di copertura applicativa.
La suite aggiornata è interamente verde; una nuova misura monolitica della copertura non
ha terminato correttamente in questo ambiente dopo la conclusione dei test. GitHub CI
resta il gate definitivo per la nuova misura.

## Limiti e bloccanti

- `pip-audit` è installato, ma non ha potuto raggiungere PyPI per errore DNS locale;
  il workflow GitHub eseguirà l'audit con accesso Internet.
- Windows installer e stack Docker completo devono essere costruiti e provati sui runner
  GitHub e poi su macchine reali.
- Il nome `ThisTinti` non ha ancora superato una clearance ufficiale; dominio e marchio
  sono sospesi fino alla decisione sul nome definitivo.
- Revisione legale esterna, security review indipendente e pilot reale restano necessari
  prima di chiamare la release stabile.

## Materiale aggiunto

- guida semplice;
- kit pilot;
- checklist di pubblicazione;
- verifica preliminare del nome e piano dominio;
- revisione preliminare licenze e inventario CSV;
- brief per avvocato e revisore di sicurezza;
- gate automatico di publication readiness;
- pagina pubblica ampliata con stato alpha, limiti e documentazione.
