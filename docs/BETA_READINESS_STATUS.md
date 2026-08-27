# Stato di preparazione alla beta

## Definizioni

- **Public Preview alpha/RC**: release pubblica verificata tecnicamente, destinata a demo, valutazione e pilot supervisionati.
- **Beta tecnica candidata**: il codice, la distribuzione e le procedure interne superano i gate automatici e sono adatti a un pilot controllato.
- **Beta validata**: oltre ai gate tecnici, esistono evidenze reali e indipendenti su accuratezza, sicurezza, privacy, accessibilità ed operazioni.
- **Produzione / 1.0 Stable**: non è implicata dalla parola beta e richiede il completamento dei gate tecnici, umani ed esterni e una decisione formale dell'organizzazione che gestisce il sistema.

## Stato attuale

ThisTinti è pubblicato come **3.4.0-alpha.7-rc.15 — RC15 Pilot-Ready — Public Preview**. RC15 completa il workflow supervisionato di pratica, il lifecycle auditabile delle segnalazioni, il pilot workspace integrato, il profilo azienda versionato e le operazioni esplicite di export, archivio e cancellazione.

RC15 ha superato i gate tecnici automatici sul commit applicativo `0c99155d17374ce195db4ec65200a8edcf1bcdd1`, incluso il ciclo Windows RC14→RC15, ed è stata pubblicata come prerelease verificata. Resta una **Public Preview supervisionata**, non una beta validata: pilot reale, revisioni indipendenti, accessibilità manuale, infrastruttura definitiva, firma Authenticode e test con utenti non istruiti restano gate esterni aperti.

La base tecnica verificata comprende:

- test applicativi e copertura minima prevista dal gate;
- migrazioni reversibili;
- PostgreSQL con ruoli separati e RLS;
- prova self-hosted con backup, ripristino e riavvio;
- ciclo Windows di installazione, aggiornamento e disinstallazione con conservazione dei dati;
- smoke test dell’eseguibile congelato e dell’app installata;
- Diagnostica eseguita contro il vero `ThisTinti.exe` installato;
- dependency audit, SBOM, checksum, provenienza e attestazioni;
- governance del Validation Lab e validatore preventivo dei dataset pilota;
- controlli automatici di accessibilità strutturale, tastiera/reflow di regressione e prestazioni di base;
- esperienza iniziale semplificata con anteprima, guida permanente e progressive disclosure;
- validazione numerica fail-closed e gestione leggibile degli input documentali non validi;
- evidenze apribili dal caso fino al documento originale e alla riga estratta;
- severità `critical` distinta e ordinata prima delle altre priorità;
- centro attività persistente con stato, errore, retry, cancellazione e rielaborazione guidata;
- collegamenti proposti spiegati e collegamento/scollegamento manuale con rianalisi;
- browser E2E dei flussi di recupero e collegamento contro API, database e worker reali;
- identità di build incorporata negli artefatti e verificata insieme alla provenienza;
- protocollo di pilot senza telemetria;
- estrazione OCR prudente con valori numerici fail-closed e confronto dei totali;
- toolkit pilot locale senza comunicazioni o azioni esterne automatiche;
- centro operativo con pratiche raggruppate, priorità spiegata e storico della revisione;
- correzione supervisionata delle righe estratte con audit, provenienza e rianalisi;
- suggerimenti di apprendimento non automatici e vincolati a decisioni umane sufficienti;
- pre-pilot sintetico riproducibile di 30 pratiche, usato esclusivamente come regressione tecnica;
- corpus esterno/raw congelato di 22 documenti con ground truth separata e valutazione semantica prudente;
- prova Windows dedicata dell'aggiornamento con la precedente applicazione realmente in esecuzione;
- intake RC15 con stati espliciti di acquisizione, revisione, rifiuto, blocco e fuori perimetro;
- lifecycle RC15 delle segnalazioni con riapertura, motivazioni e storico immutabile delle decisioni;
- pilot workspace RC15 con autorizzazione, due riferimenti revisore, ground truth versionata e report riproducibile;
- profilo azienda RC15 versionato e lifecycle della pratica con export verificabile, archivio e cancellazione esplicita.

## Gate interni

I gate interni sono verificati da `scripts/check_beta_readiness.py` e dai workflow dedicati. Devono restare verdi sul commit esatto candidato alla distribuzione. Le evidenze automatiche vengono associate a run e commit; ogni modifica del prodotto richiede una nuova esecuzione completa per essere promossa.

Le Public Preview storiche non vengono modificate silenziosamente: RC15 usa il proprio tag, commit applicativo, tree Git, artefatti e catena di verifica separata dalle release precedenti.

## Gate umani ed esterni non autocertificabili

La beta non può essere dichiarata validata senza:

1. collaudo umano end-to-end della release installata;
2. almeno 30 scenari documentali reali, autorizzati e anonimizzati quando necessario;
3. ground truth definita prima dell'esecuzione da revisori competenti;
4. rapporto pilot revisionato con precisione, richiamo, falsi positivi e falsi negativi;
5. penetration test indipendente e chiusura/retest dei rilievi critici o alti;
6. revisione professionale di privacy, condizioni d'uso, licenze e nome/marchio;
7. collaudo WCAG 2.2 AA con tecnologie assistive e verifica manuale/professionale;
8. prova di carico, backup e ripristino sull'infrastruttura definitiva;
9. firma Authenticode degli artefatti Windows destinati a utenti non tecnici;
10. sessioni con utenti non istruiti che confermino la comprensione del primo percorso;
11. accettazione formale dei rischi residui per il perimetro operativo previsto.

Lo stato dei gate esterni è registrato in `docs/evidence/beta/external-gates.json`. Un valore `false` è un blocco intenzionale e veritiero, non un difetto del controllo.

## Regola di rilascio

Finché almeno un gate umano o esterno resta aperto, il prodotto può essere distribuito come Public Preview alpha/RC per demo, valutazione o pilot supervisionati. Non deve essere descritto come certificato, infallibile, beta validata, pronto per qualsiasi azienda o idoneo a decisioni economiche autonome.
