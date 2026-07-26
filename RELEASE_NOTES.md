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
- aggiornamento supportato dalla RC5 con conservazione dei dati locali.

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
