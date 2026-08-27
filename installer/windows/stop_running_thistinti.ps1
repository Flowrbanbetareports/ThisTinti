[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$InstallDir,
  [int]$TimeoutSeconds = 12
)

$ErrorActionPreference = "Stop"
$TargetExe = [System.IO.Path]::GetFullPath((Join-Path $InstallDir "ThisTinti.exe"))

function Get-InstalledThisTintiProcesses {
  @(
    Get-Process -Name "ThisTinti" -ErrorAction SilentlyContinue |
      Where-Object {
        try {
          $_.Path -and ([System.IO.Path]::GetFullPath($_.Path) -ieq $TargetExe)
        } catch {
          $false
        }
      }
  )
}

if (-not (Test-Path $TargetExe)) {
  exit 0
}

$Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
do {
  $Processes = Get-InstalledThisTintiProcesses
  if ($Processes.Count -eq 0) {
    exit 0
  }

  foreach ($Process in $Processes) {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
  }

  Start-Sleep -Milliseconds 250
} while ([DateTime]::UtcNow -lt $Deadline)

$Remaining = Get-InstalledThisTintiProcesses
if ($Remaining.Count -gt 0) {
  $Ids = ($Remaining | ForEach-Object { $_.Id }) -join ", "
  Write-Error "ThisTinti is still running from $TargetExe (PID: $Ids)"
  exit 21
}

exit 0
