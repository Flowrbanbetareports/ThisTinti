# Registro di esecuzione 3.4.0-alpha.7-rc.7

Questo registro separa fatti automatici, controlli manuali e gate esterni. I
campi non ancora provati restano esplicitamente aperti.

## Candidato

| Voce | Evidenza |
|---|---|
| Versione | `3.4.0-alpha.7-rc.7` |
| Commit candidato | da registrare dopo il merge finale in `main` |
| Tree candidato | da registrare dopo il merge finale in `main` |
| Workflow CI | da eseguire sul commit candidato |
| Workflow browser | da eseguire sul commit candidato |
| Workflow Windows | da eseguire sul commit candidato |
| Artifact Windows | da scaricare e verificare |
| SHA-256 installer | da verificare |
| SHA-256 portable | da verificare |

## Risultati interni richiesti

- [ ] `make verify` verde da sorgente pulito;
- [ ] copertura combinata almeno 90%, senza esclusioni aggiunte per la RC7;
- [ ] CI, compatibilità Python, dipendenze e prova PostgreSQL verdi;
- [ ] prova self-hosted verde;
- [ ] browser E2E verde con `api_mocked: false`;
- [ ] retry e reprocess completati da worker reali;
- [ ] collegamento e scollegamento manuale persistenti;
- [ ] reflow equivalente 125%, 150% e 200% senza overflow della pagina;
- [ ] build Windows associata al commit e tree esatti;
- [ ] upgrade dalla baseline pubblicata, riavvio, persistenza e disinstallazione verdi;
- [ ] `BUILD-IDENTITY.json`, checksum, smoke report e provenienza coerenti.

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
