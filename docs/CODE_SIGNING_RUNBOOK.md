# Runbook di firma Windows

## Obiettivo

Gli installer ufficiali destinati a utenti non tecnici devono mostrare un publisher verificabile e mantenere una firma valida grazie a timestamp attendibile.

## Requisiti

- certificato Authenticode intestato al soggetto che pubblica il software;
- chiave privata custodita fuori dal repository e dai log;
- accesso limitato all'ambiente di release protetto;
- timestamp RFC 3161 di un'autorità attendibile;
- procedura documentata di rinnovo, revoca e rotazione di emergenza.

## Flusso

1. costruire gli artefatti da un tag protetto;
2. verificare test, checksum, SBOM e provenienza;
3. firmare `ThisTinti.exe`, installer e uninstaller quando tecnicamente supportato;
4. verificare con `Get-AuthenticodeSignature` e `signtool verify /pa /all /v`;
5. ricalcolare e pubblicare i checksum dopo la firma;
6. provare installazione e disinstallazione su una macchina Windows pulita;
7. impedire la pubblicazione ufficiale quando una firma attesa è assente o non valida.

## Segreti CI previsti

I nomi suggeriti, da configurare soltanto nell'environment GitHub protetto della release, sono:

- `WINDOWS_SIGNING_CERT_BASE64`;
- `WINDOWS_SIGNING_CERT_PASSWORD`;
- `WINDOWS_SIGNING_TIMESTAMP_URL`.

Le pull request e i fork non devono ricevere questi segreti. Il workflow non deve stampare il certificato, la password o i dettagli della chiave.

## Stato

La pipeline è predisposta per provenienza, checksum e verifica degli artefatti. La firma resta un gate esterno finché non viene acquisito un certificato e completata la verifica su Windows pulito.
