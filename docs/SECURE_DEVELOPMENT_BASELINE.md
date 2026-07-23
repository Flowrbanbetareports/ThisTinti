# Baseline di sviluppo sicuro

## Standard di riferimento

- OWASP ASVS 5.0.0 per requisiti applicativi verificabili;
- NIST SP 800-218 SSDF 1.1 come baseline stabile del ciclo di sviluppo;
- bozza NIST SSDF 1.2 monitorata, senza dichiararne conformità finché non è definitiva;
- WCAG 2.2 per accessibilità dell'interfaccia;
- SLSA 1.2 e attestazioni GitHub/Sigstore per la provenienza degli artefatti.

## Controlli già automatizzati

- lint, formattazione, compilazione e test con copertura minima;
- Bandit e audit delle dipendenze;
- migrazioni upgrade/downgrade;
- test SQLite, PostgreSQL, RLS e isolamento tenant;
- smoke HTTP, worker, persistenza, backup e restore;
- SBOM, checksum e ricerca di segreti;
- installer Windows con aggiornamento e disinstallazione verificati.

## Controlli da mantenere manuali o indipendenti

- threat modeling per nuove funzioni;
- review di autorizzazione e confini tenant;
- penetration test autenticato e non autenticato;
- verifica della configurazione dell'infrastruttura finale;
- analisi delle dipendenze non Python e dei tool di build;
- triage documentato delle vulnerabilità;
- test di accessibilità con tecnologie assistive;
- revisione delle dichiarazioni commerciali e legali.

## Regola di rilascio

Un artefatto è pubblicabile soltanto se la build proviene da un commit identificato, i gate automatici sono verdi, i checksum sono generati nello stesso workflow e non esistono finding critici o alti senza accettazione esplicita. L'attestazione di provenienza dimostra l'origine della build, non la sicurezza del contenuto.
