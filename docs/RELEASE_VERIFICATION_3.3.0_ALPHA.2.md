# ThisTinti 3.3.0-alpha.2 — Legal hardening verification

## Obiettivo

Questa release aggiunge barriere legali, operative e comunicative alla Local Free Edition. Non promette “responsabilità zero”: nessun testo può eliminare norme inderogabili, dolo, colpa grave o responsabilità dipendenti dai fatti concreti.

## Tutele implementate

- Apache License 2.0 preservata come licenza del codice;
- `TERMS_OF_USE.md` con scopo previsto, verifica umana, responsabilità dell’utilizzatore, dati locali, sicurezza, assenza di garanzia, limiti di responsabilità e modifiche di terzi;
- `DISCLAIMER.md`, `PRIVACY.md` e `TRADEMARKS.md` separati e visibili;
- doppia accettazione nell’installer: licenza/avviso e specifica approvazione delle clausole rilevanti;
- doppia accettazione al primo avvio della versione portable;
- registrazione locale dell’accettazione con versione, data e hash, senza trasmissione all’autore;
- controllo server-side durante la creazione del primo spazio locale;
- avviso permanente nell’interfaccia e accanto alla simulazione economica;
- pagina legale locale accessibile dal programma;
- sito con download bloccato fino alla presa visione dell’avviso;
- GitHub Release con avviso e documenti legali allegati;
- chiara separazione tra distribuzione ufficiale e fork/integrazioni di terzi;
- gate automatico `scripts/check_legal_distribution.py`.

## Verifiche concluse

- 141 test superati;
- copertura applicativa 90%, soglia bloccante rispettata;
- Ruff, format, Bandit, compileall e sintassi JavaScript superati;
- migrazioni SQLite upgrade → downgrade → upgrade superate;
- Validation Gate: 6 scenari, precisione/recall/F1 pari a 1,0;
- smoke HTTP: demo, dashboard, readiness e audit validi;
- Local Edition: documento elaborato dal worker, arresto, riavvio e persistenza verificati;
- coerenza delle barriere legali verificata automaticamente.

## Limiti dichiarati

- L’installer Inno Setup aggiornato non è stato compilato in questa sessione Linux. Il workflow Windows lo compilerà e testerà dopo la pubblicazione su GitHub.
- Le tutele riducono il rischio ma non garantiscono immunità da contestazioni.
- Prima della prima pubblicazione pubblica stabile è prudente una revisione una tantum da parte di un avvocato italiano esperto di software, sul testo finale, sul nome del distributore e sul modello effettivo di pubblicazione.
- Ogni futura monetizzazione, telemetria, cloud, assistenza promessa, accesso remoto o automazione economica richiede una nuova analisi.

## Riferimenti di progettazione

La struttura tiene conto delle sezioni 7–9 della Apache License 2.0, dei limiti italiani alle clausole di esonero e della specifica approvazione delle condizioni onerose, nonché del trattamento europeo previsto per software libero/open source fornito fuori da attività commerciale. L’applicabilità concreta e l’evoluzione normativa devono essere ricontrollate al momento della pubblicazione.
