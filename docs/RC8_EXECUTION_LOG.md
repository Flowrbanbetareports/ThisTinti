# Registro di esecuzione 3.4.0-alpha.7-rc.8

Questo registro separa fatti automatici, accettazione umana e gate esterni. I
campi non ancora provati restano esplicitamente aperti.

## Candidato

| Voce | Evidenza |
|---|---|
| Versione | `3.4.0-alpha.7-rc.8` |
| Funzione diagnostica integrata | PR `#68`, merge `dc28eac094bd779334f0fe47461595712a574d1b` |
| Commit candidato versione | `a2a0d76121326bf08ba14de30ed32de379aa28b4` (merge PR `#71`) |
| Tree candidato | `5aee4fbafe37d4698c8a3691447fd41805982142` |
| CI candidata | run `30710864495`, verde sul commit esatto |
| Browser candidata | run `30708365354`, verde sul commit esatto |
| Windows finale `main` | run `30710864493` (`#255`), verde sul commit e tree esatti |
| Registro build in `main` | commit bot `a299e38a831734a51a0a56770441861ff09fc3ac` |
| Artifact Windows | ID `8821910523`, digest archivio `70eaf2069e4d07a15bc65bd5df071495e86cd4d3774366a69703512632d656e3` |
| Evidenza Diagnostica installata | ID `8821909202`, digest `b2cad0f20b78adbe29f3b1957880eea60bcfd9b24064891345cb0b8a482874d0` |
| SHA-256 installer | `ecb0e37768633b75561f0ee470e15a051f8b3fca820902bf9cd00e849fb33d3a` |
| SHA-256 portable | `f0ed7ed10a851d701ad243cf82d048877e69bec5e4360af036249b61f358833c` |
| SHA-256 self-hosted | `33e1023d7a2fd6119dd3f6c3c5936d2d40699d26855b601fe95f4ca4207da669` |

## Evidenza già verificata sulla funzione

- [x] diagnostica aperta dalla navigazione autenticata;
- [x] controllo sicuro concluso `PARZIALE` con test numerico `NON ESEGUITO`;
- [x] test attivo concluso `PASS` contro API, database e worker reali;
- [x] input `quantity: "cinque"` registrato come `parse_failed`;
- [x] verbale `thistinti.local-diagnostics.v1` scaricato e verificato;
- [x] passaggio da tastiera alla seconda azione verificato con Chromium;
- [x] reflow equivalente al 200% senza overflow globale;
- [x] preferenza di riduzione animazioni osservata;
- [x] artifact browser della PR #68: run `30707505373`, ID `8820790578`, digest `3deab405e6913d364719a440ad4ab89364a2caee875176435444ad043b95e9cf`.
- [x] la stessa prova è stata ripetuta sul commit RC8 in `main`: run `30708365354`,
  artifact ID `8821056330`, digest
  `673740fe5b0c72f5efcaead146459c6720b1308e87285419686b15414fdb114c`.
- [x] Diagnostica ripetuta dal vero `ThisTinti.exe` dopo installazione e upgrade
  Windows: controllo sicuro `PARZIALE` senza `FAIL`, controllo attivo `PASS`,
  job `parse_failed`, verbale scaricato, ordine tastiera verificato, reflow
  equivalente 125/150/200%, riduzione animazioni e persistenza dopo riavvio;
- [x] screenshot Windows ispezionati: contenuti completi, azioni utilizzabili e
  nessun overflow globale; la tabella resta confinata al proprio contenitore.

## Gate richiesti sul candidato RC8

- [x] `make verify` verde sul commit candidato;
- [x] copertura combinata almeno 90%, senza esclusioni aggiunte;
- [x] CI, compatibilità Python, audit dipendenze e prova PostgreSQL verdi;
- [x] prova self-hosted verde, run `30708365355`;
- [x] browser E2E verde con `api_mocked: false`, Diagnostica `PASS` e job
  numerico `parse_failed`;
- [x] build Windows dal commit e tree esatti;
- [x] upgrade automatico dalla baseline pubblica RC5, riavvio, persistenza e
  disinstallazione verdi;
- [x] identità, checksum, smoke report e provenienza coerenti.
- [x] la provenienza finale registra `installed_diagnostics_passed: true`.

Il workflow automatico usa volutamente la baseline pubblica RC5 registrata in
`builds/windows-upgrade-baseline.json`. L'aggiornamento dalla RC7 realmente
installata da Lorenzo resta parte del collaudo umano e non viene dichiarato
provato da questo run.

## Accettazione non sostituita dall’automazione

- [ ] collaudo di Lorenzo secondo `docs/RC8_IN_APP_ACCEPTANCE_LORENZO.md`;
- [ ] zoom browser reale 125%, 150% e 200% su Windows;
- [ ] percorso completo con sola tastiera e tecnologia assistiva;
- [ ] prova con corpus reale autorizzato.

## Gate esterni

Restano quelli registrati in `docs/evidence/beta/external-gates.json`, inclusi
pilot reale, pentest indipendente, revisione professionale legale/privacy,
accessibilità manuale e firma Authenticode. Finché restano aperti, RC8 è una
Public Preview e non una beta validata.
