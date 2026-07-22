# Verifica del rilascio 3.4.0-alpha.4

## Evidenze completate

- build e smoke test del sorgente e dell'eseguibile congelato;
- caricamento di documenti dimostrativi ed esportazione ZIP;
- arresto, riavvio e persistenza dei documenti;
- installazione Windows reale, primo avvio, accettazione legale e creazione amministratore;
- prova automatica di installazione silenziosa, aggiornamento da un installer con versione precedente e disinstallazione;
- conservazione della cartella dati dopo la disinstallazione;
- CI Python 3.11/3.12, audit dipendenze, PostgreSQL RLS e Self-Hosted Reference Proof.

## Limiti residui dichiarati

- installer non firmato digitalmente: SmartScreen può mostrare “Editore sconosciuto”;
- nessun penetration test o parere legale indipendente;
- nessuna validazione statistica su documenti aziendali reali;
- release alpha destinata a dimostrazioni e pilot controllati con dati anonimizzati e verifica umana.
