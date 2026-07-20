# ThisTinti 3.0.0 — verifica finale locale

Data: 19 luglio 2026

## Esito

Il perimetro tecnico locale della release 3.0.0 ha superato i controlli previsti.

- 61 test superati.
- Copertura complessiva: 92%.
- Ruff: pulito.
- Ruff format: pulito.
- Bandit: pulito.
- JavaScript: sintassi valida.
- Migrazioni: upgrade, check, downgrade e nuovo upgrade riusciti.
- Validation Gate: precisione 1.0, recall 1.0, F1 1.0, MAE 0 sui sei scenari sintetici.
- Smoke HTTP: registrazione, sessione, CSRF, demo, dashboard, readiness e audit riusciti.
- Adaptive Discovery: profilo attività, regole automatiche, regole incerte e decisioni tenant-isolate testate.
- OpenAPI e SBOM rigenerati per la versione 3.0.0.

## Auto-configurazione verificata

ThisTinti:

1. osserva tipi e contenuti dei documenti;
2. rileva un profilo di attività con confidenza ed evidenze;
3. individua campi ricorrenti anche non previsti;
4. propone regole coerenti con i dati;
5. attiva soltanto le regole sopra soglia;
6. chiede conferma nella fascia intermedia;
7. non attiva ipotesi troppo deboli;
8. conserva correzioni e rifiuti umani;
9. rianalizza le catene dopo una decisione.

## Limiti

Le metriche perfette del Validation Gate riguardano il dataset sintetico incorporato. Non dimostrano accuratezza universale su documenti aziendali non ancora osservati. Prima di un uso produttivo con dati sensibili restano necessari un pilot con documenti anonimizzati reali, PostgreSQL live, test di carico sull'infrastruttura scelta, scansione malware aggiornata e penetration test indipendente.
