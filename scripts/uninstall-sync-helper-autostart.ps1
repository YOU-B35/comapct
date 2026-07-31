# Remove CrossHub Sync Helper autostart Scheduled Task (RC-AUTO).
param(
    [string]$TaskName = "CrossHub-Sync-Helper"
)

$ErrorActionPreference = "Stop"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Task not found: $TaskName (nothing to remove)" -ForegroundColor Yellow
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed Scheduled Task: $TaskName" -ForegroundColor Green
