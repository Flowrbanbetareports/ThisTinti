# Piano di distribuzione gratuita

La prima distribuzione pubblica usa GitHub Releases come origine verificabile dei
file. Ogni release deve contenere:

- installer Windows x64;
- archivio portable Windows x64;
- checksum SHA-256 di entrambi;
- note di rilascio;
- licenza, NOTICE, SBOM e sorgente corrispondente.

Una pagina web pubblica potrà in seguito collegare la release stabile, mostrare una
demo e spiegare i limiti. Non deve raccogliere documenti né essere necessaria per
usare il programma.

## Criteri per mostrare “Download stabile”

- workflow Windows verde;
- smoke test dell'eseguibile congelato verde;
- installazione e disinstallazione provate su almeno una macchina Windows 10 e una
  Windows 11 reali;
- apertura, registrazione locale, caricamento demo, esportazione e riavvio verificati;
- checksum pubblicati;
- assenza di segreti e dati reali nel pacchetto;
- issue note aperte per eventuali limitazioni note.

## Pubblicazione iniziale

Da un clone del bundle Git verificato, autenticare GitHub CLI e avviare:

```bash
gh auth login
bash scripts/publish_free_download.sh ThisTinti
```

Lo script crea un nuovo repository pubblico, pubblica `main`, invia il tag della
versione e prova ad abilitare GitHub Pages. Il tag avvia la build Windows e la
creazione automatica della GitHub Release. Lo script rifiuta di sovrascrivere un
repository esistente.
