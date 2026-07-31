# Install Windows logon Scheduled Task for CrossHub Sync Helper (RC-AUTO / TM-A09).
param(
    [ValidateSet("Exe", "Source", "Auto")]
    [string]$Mode = "Auto",
    [string]$TaskName = "CrossHub-Sync-Helper",
    [int]$NetworkSettleSeconds = 15,
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $Root "scripts\start-sync-helper-autostart.ps1"
if (-not (Test-Path $Launcher)) {
    throw "Launcher not found: $Launcher"
}

$ExeDir = Join-Path $Root "dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper"
$ConfigPath = Join-Path $ExeDir "config.json"
if (-not (Test-Path $ConfigPath)) {
    Write-Host "WARN: $ConfigPath missing. Run setup-sync-helper-config.ps1 first." -ForegroundColor Yellow
}

$argList = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" -Mode $Mode -NetworkSettleSeconds $NetworkSettleSeconds"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argList -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Installed Scheduled Task: $TaskName" -ForegroundColor Green
Write-Host "  trigger : At logon ($env:USERNAME)"
Write-Host "  mode    : $Mode"
Write-Host "  launcher: $Launcher"
Write-Host "  remove  : powershell -File scripts\uninstall-sync-helper-autostart.ps1"

$task = Get-ScheduledTask -TaskName $TaskName
Write-Host "  state   : $($task.State)"

if ($StartNow) {
    Write-Host "Starting task now..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 8
    try {
        $health = (Invoke-WebRequest -Uri "http://127.0.0.1:18765/health" -UseBasicParsing -TimeoutSec 5).Content
        Write-Host "  health  : $health" -ForegroundColor Green
    } catch {
        Write-Host "  health  : not ready yet ($($_.Exception.Message))" -ForegroundColor Yellow
    }
}
