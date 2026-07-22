# Contribuire a ThisTinti

## Prima di iniziare

ThisTinti è rilasciato con licenza Apache 2.0 ed è in fase alpha. Le modifiche devono preservare verifica umana, tracciabilità delle prove, isolamento dei dati e assenza di azioni economiche irreversibili.

Non inserire nel repository:

- documenti aziendali reali;
- dati personali non anonimizzati;
- password, token, chiavi API o certificati privati;
- log contenenti credenziali o contenuti riservati;
- database di produzione;
- materiale senza autorizzazione o licenza compatibile.

## Flusso raccomandato

1. aprire o collegare un issue non sensibile;
2. creare un branch dedicato;
3. installare `requirements-dev.txt`;
4. apportare una modifica circoscritta;
5. aggiungere test e dati sintetici;
6. eseguire Ruff, Bandit, la suite completa e lo smoke della distribuzione locale;
7. aggiornare OpenAPI, SBOM, notice e note di rilascio quando necessario;
8. aprire una pull request descrivendo rischi, compatibilità e verifiche;
9. attendere CI e revisione prima del merge.

## Interfaccia e branding

Le modifiche estetiche devono includere:

- comportamento responsive;
- contrasto e navigazione da tastiera;
- supporto a `prefers-reduced-motion` per le animazioni;
- verifica su app, sito, favicon e installer quando cambia il marchio;
- nessuna imitazione deliberata di prodotti o marchi di terzi.

## Parser, matching e regole

Ogni nuova conclusione economica deve indicare:

- dati sorgente utilizzati;
- trasformazioni applicate;
- confidenza o motivo deterministico;
- evidenze visibili all'utilizzatore;
- casi negativi e ambigui;
- comportamento in caso di errore.

I dati sintetici non autorizzano l'automazione su documenti reali. Le modifiche che influenzano conclusioni economiche devono restare spiegabili e supervisionate fino al superamento di un dataset reale approvato.

## Fork e personalizzazioni

I team tecnici possono adattare parser, regole, integrazioni, branding e deployment. Un fork diventa responsabilità di chi lo mantiene e i test upstream non certificano automaticamente codice o infrastruttura personalizzati. Vedere `docs/CUSTOMIZATION_GUIDE.md`.

## Sicurezza

Le vulnerabilità non devono essere descritte in issue pubblici. Seguire `SECURITY.md`.

## Release

I tag pubblicati non vengono modificati. Una correzione richiede una nuova versione, la rigenerazione di installer, portable, sorgenti, checksum, OpenAPI e SBOM e il superamento dei workflow previsti.
