param(
  [string]$ExePath = ""
)
$ErrorActionPreference = "Stop"
if (-not $ExePath) {
  $ExePath = Join-Path $PSScriptRoot "..\..\..\dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe"
  if (-not (Test-Path $ExePath)) {
    $ExePath = Join-Path $PSScriptRoot "CrossHub-Sync-Helper.exe"
  }
}
$ExePath = (Resolve-Path $ExePath).Path
$cmd = "`"$ExePath`" --protocol-start `"%1`""
$base = "HKCU:\Software\Classes\crosshub-sync-helper"
New-Item -Path $base -Force | Out-Null
Set-ItemProperty -Path $base -Name "(default)" -Value "URL:CrossHub Sync Helper"
New-ItemProperty -Path $base -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
$cmdKey = Join-Path $base "shell\open\command"
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty -Path $cmdKey -Name "(default)" -Value $cmd
Write-Host "Registered crosshub-sync-helper -> $cmd"
