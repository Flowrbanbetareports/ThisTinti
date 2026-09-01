# Runbook di firma Windows

## Obiettivo

Gli artefatti Windows ufficiali devono mostrare un publisher verificabile, mantenere una firma Authenticode valida e timestampata e restare legati all'esatto candidato Qualified.

Per `ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1`, una firma verificata su una preview, su un prerelease legacy `v3.4.0-alpha.*`/RC o su uno SHA precedente è soltanto preparazione. La prima release ufficiale Qualified è esclusivamente `v1.0.0`, non-draft e non-prerelease, ancorata allo stesso source SHA del candidato finale.

Il passaggio dalla numerazione prerelease legacy 3.4 alla linea ufficiale 1.0 non è un downgrade: le due linee hanno semantiche diverse e non devono essere mescolate nella prova di pubblicazione.

## Requisiti

- certificato Authenticode intestato al soggetto che pubblica il software;
- chiave privata custodita fuori dal repository, dai log e dai job non protetti;
- accesso limitato all'ambiente di release protetto;
- timestamp RFC 3161 di un'autorità attendibile;
- procedura documentata di rinnovo, revoca e rotazione di emergenza;
- source SHA finale completo a 40 hex già qualificato e congelato;
- tag ufficiale esatto `v1.0.0` sullo stesso source SHA;
- release GitHub `v1.0.0` non-draft e non-prerelease, anch'essa risolta allo stesso SHA.

## Flusso

1. congelare l'esatto source SHA candidato e completare i gate applicabili senza ereditare verdi da SHA differenti;
2. produrre gli artefatti Windows dal candidato congelato;
3. verificare test, checksum pre-firma, SBOM/provenienza e identità degli artefatti sullo stesso candidato;
4. firmare `ThisTinti.exe`, installer e uninstaller quando tecnicamente supportato;
5. verificare ogni artefatto richiesto sia con `Get-AuthenticodeSignature` sia con `signtool verify /pa /all /v`;
6. registrare subject e thumbprint del certificato, timestamp e SHA-256 dei byte firmati;
7. ricalcolare e pubblicare i checksum **dopo** la firma;
8. provare installazione e disinstallazione su una macchina Windows pulita e registrare il publisher mostrato da Windows;
9. creare/verificare il tag ufficiale esatto `v1.0.0` sul medesimo source SHA; non usare tag prerelease legacy come prova della release ufficiale;
10. verificare che la release GitHub `v1.0.0` sia non-draft, non-prerelease e risolva allo stesso SHA;
11. legare release record, workflow protetto, checksum post-firma e clean-Windows evidence allo stesso candidato;
12. impedire la pubblicazione ufficiale quando firma, timestamp, publisher, checksum, source SHA, tag o release identity non coincidono.

## Evidence manifest

`docs/qualification/windows-signing-evidence.template.json` è lo scheletro non probatorio. Finché contiene `PREPARATION_ONLY`, placeholder o gate esterni `false`, non dimostra che la firma sia avvenuta.

La verifica strutturale è eseguibile con:

```text
python scripts/validate_windows_signing_evidence.py docs/qualification/windows-signing-evidence.template.json
```

Per un record finale occorre creare una copia immutabile compilata con evidenze reali, impostare `status` a `VERIFIED` e usare anche `--final`. Il validator finale rifiuta, tra l'altro:

- release version diversa da `1.0.0`;
- release tag diverso dall'esatto `v1.0.0`;
- release GitHub dichiarata draft o prerelease;
- release SHA diverso dal source SHA candidato;
- applicazione o installer mancanti;
- Authenticode diverso da `Valid`;
- signer non coincidente con il certificato dichiarato;
- timestamp assente o fuori dalla finestra di validità dichiarata;
- evidenza PowerShell o SignTool mancante;
- SHA del workflow diverso dallo SHA del candidato;
- mancata installazione/disinstallazione su Windows pulito;
- publisher Windows non coincidente con il publisher dichiarato;
- gate esterni non realmente risolti.

Il validator controlla coerenza e completezza del record, **non** verifica crittograficamente un PE, non interroga GitHub per confermare la release e non trasforma dichiarazioni inserite a mano in prova. I riferimenti devono puntare a output immutabili o conservati come release evidence. Firma, timestamp, clean-Windows e release resolution restano prove da acquisire realmente.

## Cattura minima delle evidenze

Per ogni artefatto richiesto conservare almeno:

- SHA-256 calcolato **dopo** la firma;
- output di `Get-AuthenticodeSignature` con stato `Valid`, signer e timestamp;
- output di `signtool verify /pa /all /v` sullo stesso file;
- riferimento al certificato effettivamente usato, senza esportare la chiave privata;
- riferimento al run protetto che ha prodotto/pubblicato l'artefatto.

La prova Windows pulita deve essere distinta dai log di build e registrare ambiente, publisher visualizzato, esito di installazione/disinstallazione e riferimento all'evidenza. Un test su un artefatto differente non è trasferibile al candidato finale.

La prova di pubblicazione deve conservare separatamente:

- source SHA finale;
- tag `v1.0.0` e SHA a cui risolve;
- release GitHub `v1.0.0` con `draft=false` e `prerelease=false`;
- checksum manifest post-firma;
- workflow run protetto che ha prodotto gli artefatti.

## Segreti CI previsti

I nomi suggeriti, da configurare soltanto nell'environment GitHub protetto della release, sono:

- `WINDOWS_SIGNING_CERT_BASE64`;
- `WINDOWS_SIGNING_CERT_PASSWORD`;
- `WINDOWS_SIGNING_TIMESTAMP_URL`.

Le pull request e i fork non devono ricevere questi segreti. Il workflow non deve stampare certificato, password o dettagli della chiave.

## Rinnovo, revoca e rotazione

Prima della scadenza del certificato, registrare il certificato sostitutivo e la finestra di transizione senza riutilizzare o pubblicare materiale privato. In caso di compromissione sospetta, sospendere le release, revocare il certificato secondo la procedura dell'autorità emittente, ruotare i segreti dell'ambiente protetto e non considerare affidabile alcun nuovo artefatto finché la nuova catena non è verificata.

Le firme storiche timestampate devono essere conservate insieme alla relativa evidenza; la presenza di un timestamp non autorizza l'uso futuro di un certificato revocato o compromesso.

## Stato

Questa preparazione non fornisce un certificato, non effettua una signing ceremony e non prova Verified Publisher. #20 resta aperta finché gli artefatti reali dell'esatto candidato Qualified non sono firmati, verificati su Windows pulito e pubblicati come release ufficiale `v1.0.0` con identità same-SHA coerente.
