# Piano di distribuzione gratuita

La prima distribuzione pubblica usa GitHub Releases come origine verificabile dei
file. Ogni release deve contenere:

- installer Windows x64;
- archivio portable Windows x64;
- checksum SHA-256 di entrambi;
- manifesto `release-provenance.json` associato al commit e al tree Git esatti;
- rapporti di smoke dell'eseguibile congelato, installato e del ciclo installazione/aggiornamento/disinstallazione;
- note di rilascio;
- documenti legali, OpenAPI, SBOM e sorgente corrispondente.

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

## Pubblicazione di una nuova Public Preview

La build Windows non pubblica direttamente una release. Su ogni commit candidato di `main`:

1. il workflow Windows dipende dal gate completo `make verify`;
2. installa la baseline pubblicata e verificata in `builds/windows-upgrade-baseline.json`;
3. prova aggiornamento, avvio installato, riavvio, persistenza e disinstallazione con conservazione dei dati;
4. produce un artefatto con checksum, smoke report e provenienza;
5. il workflow di attestazione registra la provenienza GitHub degli asset.

Soltanto dopo il completamento di questi passaggi si avvia manualmente **Publish Public Preview Release**, fornendo
il commit completo e l'ID del workflow Windows corrispondente. Il workflow ripete `make verify`, richiede tutti i
workflow obbligatori verdi sullo stesso commit, verifica checksum, smoke report e attestazioni, quindi crea un tag
e una prerelease nuovi. Non aggiorna né sostituisce tag o release esistenti. Al termine registra l'evidenza osservata
in `builds/release-latest.json` e `builds/publication-latest.json`.
