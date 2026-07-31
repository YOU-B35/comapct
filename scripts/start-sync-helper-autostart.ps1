# Launcher used by the Windows Scheduled Task (RC-AUTO).
# Prefer packaged Sync Helper exe; fall back to source Agent when -Mode Source.
param(
    [ValidateSet("Exe", "Source", "Auto")]
    [string]$Mode = "Auto",
    [int]$HealthPort = 18765,
    [int]$NetworkSettleSeconds = 15
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ExeDir = Join-Path $Root "dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper"
$ExePath = Join-Path $ExeDir "CrossHub-Sync-Helper.exe"
$ConfigPath = Join-Path $ExeDir "config.json"
$LogDir = Join-Path $Root "backend\python\exports\agent-logs"
$LogPath = Join-Path $LogDir ("autostart-{0:yyyyMMdd}.log" -f (Get-Date))

function Write-AutoLog([string]$Message) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-HelperHealth([int]$Port) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Stop-HelperProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -eq "CrossHub-Sync-Helper.exe" -or
            ($_.Name -match "^(py|python)\.exe$" -and $_.CommandLine -match "run_agent\.py")
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                Write-AutoLog "stopped PID $($_.ProcessId) ($($_.Name))"
            } catch {
                Write-AutoLog "failed to stop PID $($_.ProcessId): $($_.Exception.Message)"
            }
        }
}

function Resolve-Mode {
    param([string]$Requested)
    if ($Requested -eq "Exe" -or $Requested -eq "Source") {
        return $Requested
    }
    if ((Test-Path $ExePath) -and (Test-Path $ConfigPath)) {
        try {
            $cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($cfg.agent_token) { return "Exe" }
        } catch {
            # fall through
        }
    }
    return "Source"
}

Write-AutoLog "autostart begin Mode=$Mode Root=$Root"
if ($NetworkSettleSeconds -gt 0) {
    Write-AutoLog "waiting ${NetworkSettleSeconds}s for network/session settle"
    Start-Sleep -Seconds $NetworkSettleSeconds
}

if (Test-HelperHealth -Port $HealthPort) {
    Write-AutoLog "helper already healthy on :$HealthPort — skip start"
    exit 0
}

$resolved = Resolve-Mode -Requested $Mode
Write-AutoLog "resolved mode=$resolved"
Stop-HelperProcesses
Start-Sleep -Seconds 2

if ($resolved -eq "Exe") {
    if (-not (Test-Path $ExePath)) {
        Write-AutoLog "ERROR missing exe: $ExePath"
        exit 2
    }
    if (-not (Test-Path $ConfigPath)) {
        Write-AutoLog "ERROR missing config: $ConfigPath"
        exit 3
    }
    Start-Process -FilePath $ExePath -WorkingDirectory $ExeDir -WindowStyle Minimized
    Write-AutoLog "started exe: $ExePath"
} else {
    if (-not (Test-Path $ConfigPath)) {
        Write-AutoLog "ERROR Source mode needs config.json at $ConfigPath (run setup-sync-helper-config.ps1)"
        exit 3
    }
    $cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $cfg.agent_token) {
        Write-AutoLog "ERROR config.json missing agent_token"
        exit 4
    }
    $javaUrl = if ($cfg.java_api_url) { $cfg.java_api_url } else { "https://www.yoto.work" }
    $runAgent = Join-Path $Root "scripts\run-agent.ps1"
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $runAgent,
            "-AgentToken", $cfg.agent_token,
            "-JavaApiUrl", $javaUrl,
            "-ForceRestart"
        ) `
        -WorkingDirectory $Root `
        -WindowStyle Minimized
    Write-AutoLog "started source agent via run-agent.ps1 java=$javaUrl"
}

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    if (Test-HelperHealth -Port $HealthPort) {
        $ok = $true
        break
    }
}
if ($ok) {
    Write-AutoLog "health ok on :$HealthPort"
    exit 0
}
Write-AutoLog "WARN health not ready on :$HealthPort within timeout"
exit 5
