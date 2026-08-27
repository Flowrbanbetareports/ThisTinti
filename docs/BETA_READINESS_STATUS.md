# Stato di preparazione alla beta

## Definizioni

- **Public Preview alpha/RC**: release pubblica verificata tecnicamente, destinata a demo, valutazione e pilot supervisionati.
- **Beta tecnica candidata**: il codice, la distribuzione e le procedure interne superano i gate automatici e sono adatti a un pilot controllato.
- **Beta validata**: oltre ai gate tecnici, esistono evidenze reali e indipendenti su accuratezza, sicurezza, privacy, accessibilità ed operazioni.
- **Produzione / 1.0 Stable**: non è implicata dalla parola beta e richiede il completamento dei gate tecnici, umani ed esterni e una decisione formale dell'organizzazione che gestisce il sistema.

## Stato attuale

ThisTinti è pubblicato come `3.4.0-alpha.7-rc.13 — Public Preview`. RC13 è un hotfix di sicurezza limitato all'aggiornamento di `pypdf` 6.14.2 → 6.15.0 per `PYSEC-2026-3655` e `PYSEC-2026-3656`; non aggiunge funzionalità o modifiche UI.

Il candidato successivo è **3.4.0-alpha.7-rc.14 — Public Preview**. RC14 incorpora gli hardening e le evidenze post-RC13 e corregge l'upgrade Windows quando una precedente installazione di ThisTinti è ancora in esecuzione. Fino alla pubblicazione immutabile della RC14, RC13 resta l'ultima release pubblicata.

La release RC13 è costruita dal commit applicativo `f7609b51aec4c358d0410ca8ff83e60485cac96c`, tree `e1a5ea29d4bbef7e1431d96fa5a5149dc4a46e3c`, con Windows run `33008478384` / build `394`. L’installer pubblicato ha SHA-256 `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`.

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
- prova Windows dedicata dell'aggiornamento con la precedente applicazione realmente in esecuzione.

## Gate interni

I gate interni sono verificati da `scripts/check_beta_readiness.py` e dai workflow dedicati. Devono restare verdi sul commit esatto candidato alla distribuzione. Le evidenze automatiche vengono associate a run e commit; ogni modifica del prodotto richiede una nuova esecuzione completa per essere promossa.

La Public Preview RC13 già pubblicata non viene modificata silenziosamente: la RC14 usa una nuova versione e una nuova catena di verifica.

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
