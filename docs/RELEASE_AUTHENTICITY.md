# Verificare l'autenticità di una release

## Canali ufficiali

Scaricare ThisTinti soltanto dalla pagina GitHub Pages ufficiale o dalla sezione Releases del repository `Flowrbanbetareports/ThisTinti`.

Non considerare ufficiali file ricevuti tramite messaggi, archivi ricondivisi, mirror, siti di terzi o fork non esplicitamente indicati dal progetto.

## Controllo SHA-256 su Windows

Ogni installer e archivio portable ufficiale è accompagnato da un file `.sha256`.

Aprire PowerShell nella cartella del download ed eseguire, adattando il nome della versione:

```powershell
Get-FileHash .\ThisTinti-Setup-3.4.0-alpha.4-x64.exe -Algorithm SHA256
Get-Content .\ThisTinti-Setup-3.4.0-alpha.4-x64.exe.sha256
```

La sequenza esadecimale mostrata da `Get-FileHash` deve coincidere esattamente con quella contenuta nel file `.sha256`.

Per il portable:

```powershell
Get-FileHash .\ThisTinti-Portable-3.4.0-alpha.4-x64.zip -Algorithm SHA256
Get-Content .\ThisTinti-Portable-3.4.0-alpha.4-x64.zip.sha256
```

In caso di differenza non eseguire il file e scaricarlo nuovamente dal canale ufficiale.

## Firma digitale

Le release alpha correnti non sono firmate con un certificato di code signing. Windows può quindi mostrare `Editore sconosciuto` e Microsoft Defender SmartScreen può richiedere una conferma aggiuntiva.

Il checksum prova che il file coincide con quello pubblicato dal progetto, ma non sostituisce una firma digitale. La firma degli artefatti è un gate previsto prima di una distribuzione commerciale o su larga scala.

## Versioni e tag

- i tag pubblicati non vengono spostati;
- una correzione genera una nuova versione;
- il numero mostrato nell'applicazione deve coincidere con installer, release e checksum;
- le evidenze di pubblicazione sono registrate in `builds/release-latest.json` e `builds/publication-latest.json`.

## Segnalazione di un file sospetto

Non allegare pubblicamente documenti aziendali, credenziali o exploit. Segnalare nome del file, origine, hash SHA-256 e comportamento osservato seguendo `SECURITY.md`.
