# ThisTinti Local Edition

## Obiettivo

La Local Edition è pensata per la distribuzione gratuita e autonoma. L'autore non
ospita il servizio, non crea account centrali, non riceve documenti e non raccoglie
telemetria. L'applicazione ascolta soltanto su `127.0.0.1` e conserva database,
file, configurazione e backup nel profilo locale dell'utente.

Su Windows i dati sono salvati in:

```text
%LOCALAPPDATA%\ThisTinti
```

La disinstallazione rimuove il programma ma conserva quella cartella, evitando la
perdita involontaria dei documenti.

## Esperienza utente

1. Installare `ThisTinti-Setup-<version>-x64.exe`.
2. Avviare **ThisTinti** dal menu Start.
3. La finestra di controllo avvia il motore locale e apre il browser.
4. Al primo avvio creare lo spazio aziendale e l'utente amministratore.
5. Chiudendo la finestra di controllo viene arrestato anche il motore locale.

La stessa release offre un archivio portable. In quel caso il programma non viene
installato, ma i dati vengono comunque salvati nel profilo dell'utente e non nella
cartella dell'eseguibile.

## Aggiornamenti e backup

Prima di applicare le migrazioni a un database esistente, il launcher crea un
backup automatico in:

```text
%LOCALAPPDATA%\ThisTinti\backups
```

Vengono mantenute le ultime cinque copie pre-aggiornamento. Gli upload rimangono
separati e non vengono cancellati dall'installer o dall'uninstaller.

## OCR

La build Windows può includere Tesseract OCR con modelli italiano e inglese e usa
PDFium come renderer integrato quando Poppler non è disponibile. Tutta
l'elaborazione avviene localmente. L'OCR rimane un'evidenza derivata e richiede
revisione umana, soprattutto su manoscritti e scansioni difficili.

## Codice sorgente e personalizzazione

Il programma include uno snapshot del sorgente corrispondente alla build. Dalla
finestra di controllo si può usare **Esporta sorgente**. La licenza Apache 2.0
consente utilizzo, modifica e redistribuzione nel rispetto delle condizioni della
licenza e delle attribuzioni.

## Limiti intenzionali

- ThisTinti non esegue pagamenti e non modifica la contabilità.
- Nessuna conclusione deve sostituire la revisione umana.
- Non è incluso supporto garantito.
- La build gratuita non è firmata digitalmente: Windows può mostrare un avviso
  SmartScreen finché il progetto non acquisisce reputazione o un certificato.
- Una postazione locale singola non sostituisce un'installazione server multiutente.

## Build riproducibile

Il workflow `.github/workflows/windows-release.yml` usa un runner Windows, esegue
test e controlli statici, crea una directory PyInstaller, esegue uno smoke test
sull'eseguibile congelato, genera installer Inno Setup e archivio portable, quindi
produce checksum SHA-256. Un tag Git pubblica gli stessi file in GitHub Releases.
