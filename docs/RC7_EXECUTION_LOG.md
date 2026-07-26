# Registro di esecuzione 3.4.0-alpha.7-rc.7

Questo registro separa fatti automatici, controlli manuali e gate esterni. I
campi non ancora provati restano esplicitamente aperti.

## Candidato

| Voce | Evidenza |
|---|---|
| Versione | `3.4.0-alpha.7-rc.7` |
| Commit candidato | `2d4480a3761085073c2e62f8f8220ad85c698440` |
| Tree candidato | `d29c9363dffde5f845508632fa03d1f5ba150703` |
| CI candidata | run `30206778431`, `success`, sul merge testato del PR 58 |
| Browser candidata | run `30206778400`, `success`, artifact `8633299853`, digest `0cff70df22aee6346accb0e1d05969751e5869d4fccb65133ec2c0fabb72b8c7` |
| Windows finale `main` | run `30207099162`, numero `238`, commit e tree candidati esatti |
| Artifact Windows | ID `8633460529`, digest `253d31bd199133a7a78c259c46821fe440a59c0913e7d5640d5463067956fddc` |
| SHA-256 installer | `27463bf90720784d1dc273fecf4a526b53b76b58ecfb319093488b232b27035b` |
| SHA-256 portable | `5b4711f5a4061da736c083c8c74ddeabce92298f6eaa683a856f6b6ea74e101e` |
| SHA-256 self-hosted | `72e5984646d6b142b70384ab808b17e0c49a48fe6971b1caebe141b3f86584c7` |

## Risultati interni richiesti

- [x] `make verify` verde da sorgente pulito nel source-verification Windows finale;
- [x] copertura combinata almeno 90%, senza esclusioni aggiunte per la RC7;
- [x] CI, compatibilità Python, dipendenze e prova PostgreSQL verdi;
- [x] prova self-hosted verde;
- [x] browser E2E verde con `api_mocked: false`;
- [x] retry e reprocess completati da due processi worker reali;
- [x] collegamento e scollegamento manuale persistenti;
- [x] reflow equivalente 125%, 150% e 200% senza overflow della pagina;
- [x] build Windows associata al commit e tree esatti;
- [x] upgrade dalla baseline RC5, riavvio, persistenza e disinstallazione verdi;
- [x] `BUILD-IDENTITY.json`, checksum, smoke report e provenienza coerenti.

Il PR 58 è stato verificato prima dello squash sul merge commit GitHub
`14a7a996cebf9296afcdad80ad40962643ea3e69`. La build Windows finale è stata
ripetuta dopo il merge sul commit `2d4480a...` e ne registra il tree esatto.
Il successivo commit bot `1b340f7f...` modifica soltanto
`builds/windows-latest.json` con questa provenienza e non è la sorgente
dell’artefatto.

## Controlli non sostituiti dall’automazione

- [ ] collaudo di Lorenzo secondo `docs/RC7_WINDOWS_ACCEPTANCE_LORENZO.md`;
- [ ] zoom browser reale 125%, 150% e 200% su Windows;
- [ ] tastiera completa e tecnologia assistiva;
- [ ] prova con corpus reale autorizzato.

## Gate esterni

Restano quelli registrati in `docs/evidence/beta/external-gates.json`, inclusi
pilot reale, pentest indipendente, revisione professionale legale/privacy,
accessibilità manuale e firma Authenticode. Finché restano aperti, RC7 è una
Public Preview e non una beta validata.
