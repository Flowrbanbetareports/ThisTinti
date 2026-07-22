# Verifica del rilascio 3.4.0-alpha.5

## Ambito

Questa release modifica esclusivamente identità visiva, motion system, pagina pubblica, icona Windows e relativi gate di distribuzione. Motore documentale, schema dati, regole economiche e limiti operativi restano invariati.

## Ordine di verifica

Il collaudo visivo viene eseguito soltanto dopo il completamento positivo dei gate automatici sullo stesso commit. Un esito grafico favorevole non può compensare test applicativi, sicurezza, packaging o persistenza falliti.

## Gate automatici richiesti

- logo applicazione e sito identici;
- monogramma doppia T e palette previsti presenti nel file SVG;
- generatore reviewable dell'icona Windows e payload ICO multi-risoluzione valido;
- JavaScript applicazione e sito sintatticamente validi;
- `prefers-reduced-motion` presente in app e pagina pubblica;
- fallback senza `IntersectionObserver`;
- suite applicativa, copertura, Ruff, Bandit e audit dipendenze;
- PostgreSQL/RLS ed Enterprise Self-Hosted Reference Proof;
- build PyInstaller e compilazione Inno Setup;
- installazione del vero installer pubblicato `v3.4.0-alpha.4`, aggiornamento alla alpha.5, smoke installato, disinstallazione e conservazione dati;
- accettazione legale silenziosa valida soltanto con il parametro esplicito `/ACCEPTTHISTINTITERMS=yes`, senza finestre bloccanti durante l'aggiornamento.

## Collaudo visivo Windows richiesto

- icona corretta in installer, menu Start e barra delle applicazioni;
- schermata di accesso e registrazione leggibili a 100%, 125% e 150% di scala;
- sidebar, dashboard e pipeline senza sovrapposizioni;
- transizioni fluide ma non bloccanti;
- comportamento coerente con animazioni ridotte abilitate in Windows;
- sito pubblico verificato su desktop e finestra mobile;
- nessuna regressione nella creazione spazio, caricamento demo, esportazione e riavvio.

## Limiti invariati

- installer non firmato digitalmente e possibile avviso SmartScreen;
- nessuna validazione statistica su documenti aziendali reali;
- nessun penetration test o parere legale indipendente;
- release alpha destinata a demo e pilot controllati con dati anonimizzati e verifica umana.
