# 3.4.0-alpha.7-rc.14 — validazione documentale e hotfix upgrade Windows — Public Preview

- consolida il benchmark controllato da 30 scenari documentali con ground truth separata e gate quantitativi riproducibili;
- aggiunge un corpus esterno “sporco” di 22 documenti pubblici/raw e una valutazione semantica separata per misurare parsing, campi, righe, astensione e segmentazione senza trasformare il corpus in materiale di training;
- irrobustisce la lettura PDF/OCR locale per identificativi documento espliciti, valuta e righe commerciali, privilegiando l’astensione rispetto a valori inventati quando l’evidenza non è sufficiente;
- rafforza backup/restore e i relativi test di persistenza;
- corregge l’aggiornamento Windows quando una precedente installazione di ThisTinti è ancora in esecuzione: l’installer chiude soltanto il processo appartenente alla cartella che sta aggiornando prima di sostituire i file;
- aggiunge una prova Windows dedicata che installa una versione precedente, la avvia realmente, la lascia in esecuzione durante l’upgrade e verifica chiusura del vecchio processo, aggiornamento, avvio, diagnostica e conservazione dati;
- rigenera i contratti OpenAPI e SBOM della RC14 dopo l’allineamento finale di versione, così i gate di release verificano gli artefatti committati contro lo stesso candidato;
- mantiene il modello local-first e supervisionato: gli output restano evidenze da verificare sui documenti originali, non decisioni o certificazioni automatiche;
- pilot reale con documenti aziendali autorizzati, pentest indipendente, revisione legale/privacy, WCAG manuale, utenti non istruiti e firma Authenticode restano gate esterni aperti.

# 3.4.0-alpha.7-rc.13 — hotfix sicurezza PDF — Public Preview

- aggiorna `pypdf` da 6.14.2 a 6.15.0 per correggere `PYSEC-2026-3655` e `PYSEC-2026-3656`;
- nessuna nuova funzionalità, nessuna modifica UI e nessun cambiamento al modello local-first;
- lock e SBOM riallineati; dependency audit, test parser/PDF, CI completa e ciclo Windows rieseguiti sul commit esatto;
- pubblicata come Public Preview prerelease `v3.4.0-alpha.7-rc.13` il 2026-08-26 dopo verifica completa sul commit `f7609b51aec4c358d0410ca8ff83e60485cac96c`, tree `e1a5ea29d4bbef7e1431d96fa5a5149dc4a46e3c` e Windows run `33008478384` / build `394`;
- installer `ThisTinti-Setup-3.4.0-alpha.7-rc.13-x64.exe`, SHA-256 `505532c67d324a29487d77acd9ae0d1f1e5b918a4f2ccbb996bc3b2be774622f`;
- RC12 resta immutabile come release storica; RC13 è la Public Preview corrente;
- pilot reale, pentest indipendente, revisione legale/privacy, WCAG manuale, utenti non istruiti e firma Authenticode restano gate esterni aperti.

# 3.4.0-alpha.7-rc.12 — preparazione commerciale leggera

- nuova pagina amministratore “Progetto e piani”, separata dal lavoro documentale quotidiano;
- contatore dei download pubblici GitHub per installer, portable e self-hosted, dichiarato esplicitamente distinto da utenti e installazioni attive;
- riepilogo di release, stelle, fork, issue/PR e workflow pubblici richiesto soltanto quando l’amministratore apre o aggiorna la pagina;
- Integration Pack in anteprima con OpenAPI, esempi Python, JavaScript e C# e contratto tecnico di esportazione;
- catalogo minimo Free / Integration Pack / Enterprise senza prezzi o checkout attivi;
- spazio sponsor esclusivamente dimostrativo, privo di reti esterne, profilazione e inserzioni nelle schermate operative;
- politica di acquisto digitale futura predisposta senza rinunce assolute a reclami legittimi o diritti inderogabili;
- nessuna telemetria, nessun documento o dato utente inviato all’autore;
- pubblicata come Public Preview immutabile `v3.4.0-alpha.7-rc.12` dopo i gate completi, con checksum, provenienza e attestazioni sul commit applicativo verificato; i gate esterni di beta/produzione restano aperti.

# 3.4.0-alpha.7-rc.11 — centro operativo e revisione supervisionata

- la home indica cosa controllare adesso e propone la prossima verifica in base a gravità, stato, valore indicativo e data;
- le segnalazioni della stessa operazione vengono raggruppate in un unico fascicolo di pratica;
- il workflow distingue nuova, in verifica, confermata, falso positivo e risolta, mantenendo lo storico delle decisioni;
- il confronto della pratica riusa le prove e i documenti collegati esistenti senza creare copie o fonti parallele;
- i revisori possono correggere una riga estratta con motivo obbligatorio, prima/dopo, autore, provenienza e rianalisi delle catene coinvolte;
- i totali vengono ricalcolati coerentemente quando quantità, prezzo o sconto vengono corretti;
- i decimali di memorizzazione non compaiono più nelle nuove descrizioni e nelle evidenze;
- il rapporto operativo è esportabile in JSON e in una vista stampabile/PDF, lasciando nulli i dati di pilot non realmente misurati;
- l’apprendimento propone una revisione delle soglie soltanto dopo almeno cinque decisioni umane coerenti e non applica mai modifiche automatiche;
- Chromium verifica sia la presentazione isolata sia il flusso reale contro API, database, audit e rianalisi;
- pubblicata come Public Preview immutabile dopo i gate completi sul commit candidato e sull’installer Windows verificato.

# 3.4.0-alpha.7-rc.10 — qualità del prodotto e linguaggio operativo

- identificatori tecnici, campi, stati e tipi di anomalia vengono tradotti in italiano comprensibile;
- quantità e percentuali non mostrano più zeri decimali inutili;
- il punteggio di rischio viene presentato come priorità di controllo e l’indice tecnico resta secondario e non probabilistico;
- l’avviso di uso supervisionato è compatto ma sempre disponibile;
- Regole proposte, Validation Lab e Audit assumono nomi e spiegazioni più vicine al loro scopo reale;
- il pulsante demo scompare dopo che esistono documenti e la pagina Attività distingue elaborazioni persistenti dagli altri eventi applicativi;
- i payload di audit restano disponibili dietro un dettaglio tecnico richiudibile;
- la nuova presentazione è isolata dal core di sicurezza, non usa servizi esterni e non invia messaggi;
- un controllo Chromium reale verifica gerarchia, terminologia, numeri, rischio, audit e visibilità della demo;
- un gate impedisce ai moduli già monolitici di continuare a crescere senza estrazione;
- pubblicata come Public Preview immutabile dopo CI, Chromium, PostgreSQL, self-hosted, ciclo Windows, checksum, provenienza e attestazioni verdi sul commit esatto.

# 3.4.0-alpha.7-rc.9 — OCR strutturato e pilot esclusivamente locale

- le fatture PDF con campi etichettati possono produrre righe revisionabili da SKU, descrizione, quantità, prezzo unitario, sconto e totale;
- fornitore, riferimento ordine e riferimento consegna vengono acquisiti soltanto quando esplicitamente indicati;
- i valori numerici OCR non validi restano fail-closed e riportano riga, campo, valore e motivo;
- il totale indicato nel documento viene confrontato con quello ricalcolato, con revisione obbligatoria in caso di differenza;
- le righe derivate da OCR mantengono provenienza e confidenza prudente e non diventano decisioni automatiche;
- il benchmark abbigliamento blocca regressioni se le scansioni sintetiche pulite o a basso contrasto non producono almeno una riga utile;
- il toolkit per pilot reale resta locale e non contiene invio email, contatti automatici o azioni verso fornitori;
- pubblicata come Public Preview immutabile dopo i gate completi sul commit candidato e sull’installer Windows verificato.

# 3.4.0-alpha.7-rc.8 — Diagnostica e collaudo dentro l’app

- aggiunta la voce **Diagnostica** nella navigazione autenticata;
- i controlli locali confrontano versione runtime e OpenAPI e verificano sessione, dashboard, documenti, collegamenti, segnalazioni e attività;
- il controllo sicuro non modifica i documenti e lascia il test numerico esplicitamente `NON ESEGUITO`;
- il test attivo carica tramite la normale UI un JSON con quantità `cinque` e richiede un job `parse_failed` con campo, valore e motivo consultabili;
- gli esiti pubblici sono coerenti: `PASS`, `PARZIALE`, `FAIL` e `NON ESEGUITO`;
- il verbale JSON è scaricabile e non contiene token né copie dei documenti aziendali;
- la pagina non usa telemetria, servizi cloud o connessioni esterne;
- il browser E2E apre la diagnostica dall’app autenticata, usa la tastiera, avvia il worker reale, scarica il verbale e verifica reflow equivalente al 200% e riduzione animazioni;
- la diagnostica non viene presentata come prova WCAG, pentest, pilot o certificazione indipendente;
- questa versione resta una Public Preview alpha/RC e richiede accettazione umana prima della pubblicazione.

# 3.4.0-alpha.7-rc.7 — Evidenze reali, reflow e provenienza del download

- i test browser di recupero e collegamento usano API, database e worker reali, senza risposte simulate;
- retry, rielaborazione con metadati corretti e collegamento/scollegamento manuale vengono verificati fino alla persistenza;
- le catene documentali si aprono anche da tastiera;
- la schermata Attività mantiene leggibili errori e azioni al viewport desktop di riferimento;
- il layout evita overflow della pagina ai viewport equivalenti a zoom 125%, 150% e 200%;
- la navigazione ridotta resta compatta, etichettata e scorrevole orizzontalmente;
- ogni portable incorpora `BUILD-IDENTITY.json` con versione, commit, tree, workflow e nome dell’artefatto;
- checksum e provenienza rifiutano un portable ricalcolato se dichiara un’altra sorgente;
- una guida inclusa nel download spiega verifica, provenienza e limite dell’eseguibile non firmato;
- nomi e descrizioni distinguono verifiche euristiche, simulazioni supervisionate e decisioni umane;
- questa versione resta una Public Preview: zoom reale su Windows, tecnologie assistive, pilot e revisioni indipendenti non sono autocertificati.

# 3.4.0-alpha.7-rc.6 — Integrità dati, recupero ed evidenze correggibili

- i valori numerici invalidi, non finiti o non convertibili non vengono più trasformati silenziosamente in zero;
- gli input documentali non validi producono errori leggibili e non HTTP 500 generici;
- il gate completo `make verify` è bloccante per CI, build Windows e pubblicazione;
- OpenAPI, SBOM, versione, installer e provenienza vengono verificati sullo stesso commit candidato;
- le segnalazioni permettono di aprire il documento originale e la riga estratta che ha generato l’evidenza;
- i casi `critical` sono distinti, contati e ordinati prima delle altre severità;
- aggiunto il centro **Attività** con stato persistente, errore, tentativi, ricerca, filtri, annullamento e nuovo tentativo;
- aggiunta la correzione guidata dei metadati e la rielaborazione senza perdere l’ultima estrazione valida;
- le proposte di collegamento mostrano compatibilità, percentuale e motivazioni;
- collegamento e scollegamento manuale sono disponibili dalla UI con rianalisi della catena;
- sidebar, evidenze, recupero e collegamenti sono verificati con Chromium reale;
- il posizionamento resta quello di un workspace locale e supervisionato: le euristiche preparano evidenze e non certificano, approvano o decidono autonomamente;
- aggiornamento supportato dalla RC5 con conservazione dei dati locali;
- l’artefatto pubblico RC6 deve essere costruito dal commit finale unito in `main`, non da un ramo intermedio.

# 3.4.0-alpha.7-rc.5 — Overflow laterale reale verificato in Chromium

- corretto il pannello degli strumenti avanzati, che nelle finestre basse si restringeva e nascondeva le voci senza creare overflow nel menu esterno;
- la navigazione usa elementi non comprimibili, così l’altezza scorrevole supera realmente l’area visibile quando le voci non entrano;
- i gesti a due dita e la rotella vengono instradati dall’intera colonna blu verso il menu, senza spostare la pagina bianca;
- normalizzati i delta del dispositivo espressi in pixel, righe o pagine;
- aggiunto versionamento delle risorse CSS e JavaScript per evitare il riuso di file obsoleti dalla cache;
- aggiunto un collaudo con Chromium reale che apre gli strumenti avanzati, verifica l’overflow e simula un gesto verticale;
- nessuna modifica al motore documentale, ai dati, ai ruoli o ai controlli di sicurezza.

# 3.4.0-alpha.7-rc.4 — Scorrimento laterale verificabile

- introdotte tre aree distinte nella sidebar desktop: logo, menu e account;
- aggiunti supporto Home/End, mantenimento della voce selezionata nell’area visibile e barra di scorrimento più leggibile;
- il collaudo reale ha poi evidenziato il difetto interno corretto dalla RC5.

# 3.4.0-alpha.7-rc.3 — Primo accesso locale corretto

- il launcher distingue tra primo avvio e spazio locale già esistente;
- gli errori di accesso e registrazione vengono mostrati con testo leggibile;
- i pulsanti vengono bloccati durante la richiesta per evitare doppi invii.

# 3.4.0-alpha.7-rc.2 — Prima correzione della navigazione laterale

- introdotta un’area centrale destinata allo scorrimento;
- aggiunti scrollbar e contenimento dello scorrimento;
- il comportamento reale su finestre basse è stato completato nella RC5.

# 3.4.0-alpha.7-rc.1 — Esperienza iniziale semplificata

- aggiunta un’anteprima utilizzabile prima dell’accesso;
- introdotta la guida permanente `Carica → Collega → Controlla`;
- raccolti gli strumenti specialistici sotto **Strumenti avanzati**;
- mantenuto lo stato **Public Preview alpha/RC** con verifica umana obbligatoria.

Le note dettagliate delle versioni precedenti restano consultabili nella cronologia del repository e nelle relative release GitHub.
