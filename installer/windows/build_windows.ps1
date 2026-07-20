$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")

$Version = (Select-String -Path "app\version.py" -Pattern 'RELEASE_VERSION = "([^"]+)"').Matches.Groups[1].Value
if (-not $Version) { throw "Versione non rilevata" }

python -m PyInstaller --clean --noconfirm "installer\windows\ThisTinti.spec"
if ($LASTEXITCODE -ne 0) { throw "Creazione eseguibile PyInstaller fallita" }

# Bundle a local OCR engine when the build environment provides it. The pinned
# Chocolatey package is used only during build; the installed app makes no network calls.
choco install tesseract --version=5.5.0.20241111 --yes --no-progress
if ($LASTEXITCODE -ne 0) { throw "Installazione Tesseract fallita" }
$Tesseract = Join-Path $env:ProgramFiles "Tesseract-OCR"
if (-not (Test-Path $Tesseract)) { $Tesseract = Join-Path ${env:ProgramFiles(x86)} "Tesseract-OCR" }
if (-not (Test-Path $Tesseract)) { throw "Tesseract non trovato dopo l'installazione" }
$OcrTarget = "dist\ThisTinti\_internal\ocr\tesseract"
New-Item -ItemType Directory -Path $OcrTarget -Force | Out-Null
Copy-Item "$Tesseract\*" $OcrTarget -Recurse -Force

$TesseractExe = Join-Path $OcrTarget "tesseract.exe"
if (-not (Test-Path $TesseractExe)) { throw "Eseguibile Tesseract assente dal runtime" }
$EnglishData = Join-Path $OcrTarget "tessdata\eng.traineddata"
if (-not (Test-Path $EnglishData) -or (Get-Item $EnglishData).Length -lt 1000000) {
  throw "Modello OCR inglese non valido"
}
$ItalianData = Join-Path $OcrTarget "tessdata\ita.traineddata"
if (-not (Test-Path $ItalianData)) {
  $ItalianModelUrl = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/ita.traineddata"
  for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
    try {
      Invoke-WebRequest -Uri $ItalianModelUrl -OutFile $ItalianData
      break
    } catch {
      if ($Attempt -eq 3) { throw }
      Start-Sleep -Seconds (2 * $Attempt)
    }
  }
}
if ((Get-Item $ItalianData).Length -lt 1000000) { throw "Modello OCR italiano non valido" }
$BundledLicense = Get-ChildItem $OcrTarget -File | Where-Object { $_.Name -match '^LICENSE' } | Select-Object -First 1
if ($BundledLicense) {
  Copy-Item $BundledLicense.FullName (Join-Path $OcrTarget "TESSERACT-LICENSE.txt") -Force
} else {
  # Tesseract and tessdata_fast use Apache-2.0; preserve the full license text.
  Copy-Item "LICENSE" (Join-Path $OcrTarget "TESSERACT-LICENSE.txt") -Force
}

# Smoke-test the exact frozen app and worker, including persistence after restart.
New-Item -ItemType Directory -Path "release\windows" -Force | Out-Null
$SmokeData = "build\windows-smoke-data"
Remove-Item $SmokeData -Recurse -Force -ErrorAction SilentlyContinue
python scripts\local_distribution_smoke.py `
  --executable "dist\ThisTinti\ThisTinti.exe" `
  --data-dir $SmokeData `
  --report "release\windows\frozen-local-smoke.json"
if ($LASTEXITCODE -ne 0) { throw "Smoke test dell'eseguibile Windows fallito" }
Remove-Item $SmokeData -Recurse -Force -ErrorAction SilentlyContinue

$Portable = "release\windows\ThisTinti-Portable-$Version-x64.zip"
Remove-Item $Portable -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "dist\ThisTinti\*" -DestinationPath $Portable -CompressionLevel Optimal

choco install innosetup --yes --no-progress
if ($LASTEXITCODE -ne 0) { throw "Installazione Inno Setup fallita" }
$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) { $Iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $Iscc)) { throw "Compilatore Inno Setup non trovato" }
& $Iscc "/DMyAppVersion=$Version" "installer\windows\ThisTinti.iss"
if ($LASTEXITCODE -ne 0) { throw "Compilazione installer fallita" }

Copy-Item "TERMS_OF_USE.md", "DISCLAIMER.md", "PRIVACY.md", "TRADEMARKS.md" "release\windows" -Force

Get-ChildItem "release\windows\*.exe", "release\windows\*.zip" | ForEach-Object {
  $Hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$Hash  $($_.Name)" | Set-Content "$($_.FullName).sha256" -Encoding ascii
}
Get-ChildItem "release\windows" | Format-Table Name, Length
