# Matrice delle responsabilità — Self-Hosted Reference Edition

Questa matrice chiarisce il confine operativo. Non sostituisce una valutazione legale o contrattuale dell’organizzazione.

| Area | Progetto open source | Organizzazione / operatore / fornitore scelto |
|---|---|---|
| Codice di riferimento | Pubblica sorgente, test e documentazione senza garanzia | Valuta idoneità, modifica e convalida il proprio fork |
| Hosting e cloud | Nessun hosting gestito | Seleziona, paga e amministra infrastruttura e fornitori |
| Dati e privacy | Non riceve i documenti nelle configurazioni ufficiali | Determina ruoli, basi giuridiche, conservazione e misure privacy |
| Sicurezza | Fornisce controlli di base e configurazione di riferimento | Hardening, patching, scansioni, segreti, firewall, accessi e penetration test |
| Disponibilità | Nessun SLA o reperibilità | Monitoraggio, capacità, ridondanza, continuità e disaster recovery |
| Backup | Fornisce script di riferimento | Pianifica, esegue, cifra, conserva e prova il ripristino |
| Aggiornamenti | Può pubblicare release senza obbligo | Decide tempi, testa compatibilità e applica aggiornamenti |
| Supporto | Nessun help desk garantito | Usa personale interno o contratta fornitori indipendenti |
| Integrazioni | Espone codice e API | Realizza, testa e mantiene ERP, SSO, storage e plugin |
| Risultati | Segnala possibili anomalie | Verifica sempre originali e mantiene controllo umano |
| Incidenti | Nessuna gestione dell’installazione | Rileva, contiene, analizza, notifica e ripristina |
| Costi | Nessun canone del progetto | Sostiene cloud, hardware, domini, certificati, tecnici e servizi |

Il file `operator-acceptance.json` registra localmente che l’operatore ha preso visione di questo confine. Non viene trasmesso all’autore e non crea un servizio gestito.
