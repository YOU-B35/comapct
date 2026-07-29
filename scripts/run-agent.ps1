# CrossHub Agent launcher (token injected by downloaded .bat)
param(
    [string]$AgentToken = $env:AGENT_TOKEN,
    [string]$JavaApiUrl = $env:JAVA_API_URL,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $Root "backend\python"

if ($AgentToken) {
    $env:AGENT_TOKEN = $AgentToken
}
if ($JavaApiUrl) {
    $env:JAVA_API_URL = $JavaApiUrl
}

if (-not $env:AGENT_TOKEN) {
    Write-Host "Missing AGENT_TOKEN. Download CrossHub-Sync-Helper.bat from CrossHub settings or Temu page." -ForegroundColor Red
    exit 2
}

Set-Location $Root
$agentScript = Join-Path $Root "backend\python\scripts\run_agent.py"
if (-not (Test-Path $agentScript)) {
    Write-Host "Agent script not found: $agentScript" -ForegroundColor Red
    exit 3
}

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python launcher 'py' not found. Install Python 3 and retry." -ForegroundColor Red
    exit 4
}

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^(py|python)\.exe$" -and
        $_.CommandLine -match "run_agent\.py"
    }

if ($existing -and -not $ForceRestart) {
    Write-Host "Agent is already running. Use -ForceRestart to restart it." -ForegroundColor Yellow
    $existing | Select-Object ProcessId, Name, CommandLine | Format-Table -AutoSize
    exit 0
}

if ($existing -and $ForceRestart) {
    Write-Host "Stopping existing agent process(es)..." -ForegroundColor Yellow
    foreach ($proc in $existing) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "  stopped PID $($proc.ProcessId)" -ForegroundColor DarkYellow
        } catch {
            Write-Host "  failed to stop PID $($proc.ProcessId): $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 1
}

Write-Host "Starting CrossHub Agent (Temu / Amazon / all platforms)..." -ForegroundColor Cyan
Write-Host "  JAVA_API_URL=$($env:JAVA_API_URL)" -ForegroundColor DarkCyan

& py -u $agentScript
