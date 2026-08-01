# Registro di esecuzione 3.4.0-alpha.7-rc.8

Questo registro separa fatti automatici, accettazione umana e gate esterni. I
campi non ancora provati restano esplicitamente aperti.

## Candidato

| Voce | Evidenza |
|---|---|
| Versione | `3.4.0-alpha.7-rc.8` |
| Funzione diagnostica integrata | PR `#68`, merge `dc28eac094bd779334f0fe47461595712a574d1b` |
| Commit candidato versione | da registrare dopo il merge della PR RC8 |
| Tree candidato | da registrare dopo il merge della PR RC8 |
| CI candidata | da registrare sul commit esatto |
| Browser candidata | da registrare sul commit esatto |
| Windows finale `main` | da registrare sul commit esatto |
| Artifact Windows | da registrare |
| SHA-256 installer | da registrare |
| SHA-256 portable | da registrare |
| SHA-256 self-hosted | da registrare |

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

## Gate richiesti sul candidato RC8

- [ ] `make verify` verde sul commit candidato;
- [ ] copertura combinata almeno 90%, senza esclusioni aggiunte;
- [ ] CI, compatibilità Python, audit dipendenze e prova PostgreSQL verdi;
- [ ] prova self-hosted verde;
- [ ] browser E2E verde con `api_mocked: false`;
- [ ] build Windows dal commit e tree esatti;
- [ ] upgrade dalla RC7, riavvio, persistenza e disinstallazione verdi;
- [ ] identità, checksum, smoke report e provenienza coerenti.

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
