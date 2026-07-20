# Checklist di pubblicazione

## Già preparato nel repository

- [x] Local Free Edition.
- [x] Self-Hosted Reference Edition.
- [x] licenza, disclaimer, privacy e politica di supporto.
- [x] installer e accettazione al primo avvio.
- [x] pagina statica senza analytics.
- [x] checksum, SBOM e workflow di release.
- [x] guide utente, backup, aggiornamento e disinstallazione.
- [x] kit pilot, brief legale e brief security review.
- [x] gate automatico di pre-pubblicazione.
- [x] ambiente con dipendenze esatte e grafo di 63 distribuzioni validato.
- [x] inventario licenze dell'ambiente di verifica.

## Bloccanti prima della prima release pubblica

- [x] adottare `ThisTinti` come nome definitivo in via preliminare;
- [ ] verificare live i domini e completare la ricerca ufficiale sui marchi simili;
- [ ] pubblicare manualmente il repository su GitHub;
- [ ] eseguire con successo workflow Windows e Docker;
- [ ] verificare gli artefatti e i checksum prodotti;
- [ ] installare su Windows 10 e Windows 11 puliti;
- [ ] collaudare la configurazione self-hosted su un server di prova;
- [ ] eseguire audit dipendenze con accesso Internet;
- [ ] chiudere eventuali vulnerabilità bloccanti.

## Prima di chiamarla stabile

- [ ] revisione legale esterna dei testi finali;
- [ ] revisione di sicurezza indipendente;
- [ ] pilot su almeno 30 pratiche reali;
- [ ] documentazione dei limiti osservati;
- [ ] scelta e acquisto del dominio;
- [ ] aggiornamento del sito con nome e dominio definitivi.

## Regola di rilascio

Finché i bloccanti non sono chiusi, usare una versione `alpha` o `beta` e non descrivere
il prodotto come certificato, infallibile, pronto per ogni azienda o idoneo ad autorizzare
decisioni economiche automatiche.
