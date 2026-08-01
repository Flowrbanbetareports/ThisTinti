# Registro di esecuzione 3.4.0-alpha.7-rc.8

Questo registro separa fatti automatici, accettazione umana e gate esterni. I
campi non ancora provati restano esplicitamente aperti.

## Candidato

| Voce | Evidenza |
|---|---|
| Versione | `3.4.0-alpha.7-rc.8` |
| Funzione diagnostica integrata | PR `#68`, merge `dc28eac094bd779334f0fe47461595712a574d1b` |
| Commit candidato versione | `ac7a8a88b59ceed5d35747ae987569d901af08bd` (merge PR `#69`) |
| Tree candidato | `9446e8ee177773ad883718d9505715d728b9f39a` |
| CI candidata | run `30708365343`, verde sul commit esatto |
| Browser candidata | run `30708365354`, verde sul commit esatto |
| Windows finale `main` | run `30708365359` (`#253`), verde sul commit e tree esatti |
| Registro build in `main` | commit bot `7744261e11201a89c44c1bad2c84333cd9e33c6c` |
| Artifact Windows | ID `8821138405`, digest archivio `d4c21381b230b2fe8bbb4804a9cee7d220d81d0f236230d0e7758bf7e4e9b8b6` |
| SHA-256 installer | `d4b2d9b6275e7021a2ea37be265fdaa9c058f7779ec4f3a67bd08ad25b59a3be` |
| SHA-256 portable | `eaea6a29a69b85c04b282d6cb0f11d5028cee75fd4cb2d622faded57ae5ac52b` |
| SHA-256 self-hosted | `11b5cfd35e9ed1027b00af99f73a338b82153a7ba4582d13545da330671a9137` |

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
