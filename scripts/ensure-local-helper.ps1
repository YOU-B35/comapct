# 确保本机 Sync Helper 真正指向本地 Java :18080（幂等）
# 由 start-local.ps1 自动调用；也可单独:
#   powershell -File scripts\ensure-local-helper.ps1
#
# 策略：优先用仓库内 Python 源码启动（始终含最新 URL 解析逻辑），
# 避免桌面 .exe 过期后仍误打 www.yoto.work。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_launcher-utils.ps1")

$PyRoot = Join-Path $Root "backend\python"
$Entry = Join-Path $PyRoot "scripts\sync_helper_app.py"
$LocalDir = Join-Path $PyRoot ".sync-helper-local"
$LocalConfig = Join-Path $LocalDir "config.json"
$LocalApi = "http://127.0.0.1:18080"

$desktopExeCandidates = @(
    "$env:USERPROFILE\Desktop\CrossHub-Sync-Helper\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe",
    "$env:USERPROFILE\Desktop\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe",
    "C:\Users\Administrator\Desktop\CrossHub-Sync-Helper\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe"
)
$desktopExe = $desktopExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

function Test-PortListen([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-HelperBindInfo {
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:18766/api/bind" -TimeoutSec 2
    } catch {
        return $null
    }
}

function Get-HelperLiveApiUrl {
    $bind = Get-HelperBindInfo
    if (-not $bind) { return "" }
    $live = [string]($bind.live_java_api_url)
    if (-not $live) { $live = [string]($bind.java_api_url) }
    return $live
}

function Test-HelperAlignedLocal {
    if (-not (Test-PortListen 18766)) { return $false }
    $bind = Get-HelperBindInfo
    if (-not $bind) { return $false }

    # Old desktop exe has no live_java_api_url — treat as misaligned so we
    # restart onto the source-tree helper (has hot-switch + correct resolve).
    $names = @($bind.PSObject.Properties.Name)
    if ($names -notcontains 'live_java_api_url') { return $false }

    $live = [string]$bind.live_java_api_url
    if ($live -match '127\.0\.0\.1:18080|localhost:18080') { return $true }

    try {
        $sw = Invoke-RestMethod -Uri "http://127.0.0.1:18766/api/dev/use-local-java" -Method POST -TimeoutSec 3
        $swLive = [string]$sw.live_java_api_url
        return [bool]($sw.ok -and ($swLive -match '127\.0\.0\.1:18080|localhost:18080'))
    } catch {
        return $false
    }
}

function Write-LocalHelperConfig {
    New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
    $obj = [ordered]@{
        java_api_url     = $LocalApi
        allow_local_java = $true
        display_name     = "本机助手-本地联调"
        start_ziniao     = $false
        health_port      = 18765
    }

    # Prefer existing local token; else copy desktop bind so no re-bind each time
    $tokenSources = @($LocalConfig)
    if ($desktopExe) {
        $tokenSources += (Join-Path (Split-Path -Parent $desktopExe) "config.json")
    }
    foreach ($src in $tokenSources) {
        if (-not (Test-Path $src)) { continue }
        try {
            $raw = Get-Content $src -Raw -Encoding UTF8
            if ($raw.Length -gt 0 -and [int][char]$raw[0] -eq 0xFEFF) { $raw = $raw.Substring(1) }
            $old = $raw | ConvertFrom-Json
            foreach ($k in @(
                    "agent_token", "token", "tenant_id", "agent_tenant_id",
                    "user_id", "bound_user_id", "machine_fingerprint", "display_name"
                )) {
                if ($old.PSObject.Properties.Name -contains $k -and $old.$k) {
                    $obj[$k] = $old.$k
                }
            }
            if ($obj.agent_token -or $obj.token) { break }
        } catch { }
    }

    $obj.java_api_url = $LocalApi
    $obj.allow_local_java = $true
    $json = ($obj | ConvertTo-Json -Depth 8)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($LocalConfig, $json, $utf8NoBom)

    # Keep desktop config aligned too (protocol may reopen desktop exe later)
    if ($desktopExe) {
        $deskCfg = Join-Path (Split-Path -Parent $desktopExe) "config.json"
        if (Test-Path $deskCfg) {
            try {
                $raw = Get-Content $deskCfg -Raw -Encoding UTF8
                if ($raw.Length -gt 0 -and [int][char]$raw[0] -eq 0xFEFF) { $raw = $raw.Substring(1) }
                $d = $raw | ConvertFrom-Json
                $d | Add-Member -NotePropertyName java_api_url -NotePropertyValue $LocalApi -Force
                $d | Add-Member -NotePropertyName allow_local_java -NotePropertyValue $true -Force
                [System.IO.File]::WriteAllText($deskCfg, ($d | ConvertTo-Json -Depth 8), $utf8NoBom)
            } catch { }
        }
    }
    Write-Host "  config → $LocalConfig" -ForegroundColor Green
}

function Stop-AllHelpers {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -match "CrossHub-Sync-Helper" -or
            ($_.CommandLine -and ($_.CommandLine -match "sync_helper_app\.py"))
        } |
        ForEach-Object {
            Write-Host "  stop helper PID $($_.ProcessId)" -ForegroundColor Yellow
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Stop-CrosshubLauncherWindows -Names @("helper")
    Start-Sleep -Seconds 1
}

# Fast path: already correct (and optionally hot-switched via /api/dev/use-local-java)
if (Test-HelperAlignedLocal) {
    Write-Host "==> Sync Helper already on local Java :18080" -ForegroundColor Green
    return
}

if (-not (Test-Path $Entry)) {
    Write-Host "==> [WARN] missing $Entry" -ForegroundColor Yellow
    return
}

Write-Host "==> ensure Sync Helper → $LocalApi (source tree)" -ForegroundColor Cyan
Stop-AllHelpers
Write-LocalHelperConfig

$helperLauncher = Join-Path $env:TEMP "crosshub-helper.ps1"
$pyCmd = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $pyCmd) {
    Write-Host "==> [WARN] Python launcher 'py' not found; cannot start local helper" -ForegroundColor Yellow
    return
}

Start-CrosshubLauncherWindow -Name "helper" -LauncherPath $helperLauncher -ScriptLines @(
    "`$env:PYTHONPATH='$PyRoot'"
    "`$env:JAVA_API_URL='$LocalApi'"
    "`$env:CROSSHUB_ALLOW_LOCAL_JAVA='1'"
    "`$env:CROSSHUB_HELPER_CONFIG='$LocalConfig'"
    "Remove-Item Env:AGENT_TOKEN -ErrorAction SilentlyContinue"
    "Set-Location '$Root'"
    "py -u '$Entry'"
)

$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline) {
    $live = Get-HelperLiveApiUrl
    if ((Test-PortListen 18766) -and ($live -match '127\.0\.0\.1:18080|localhost:18080')) {
        Write-Host "==> Sync Helper ready (local Java) live=$live" -ForegroundColor Green
        return
    }
    # Old helper without live field: try hot-switch after port is up
    if (Test-PortListen 18766) {
        try {
            $sw = Invoke-RestMethod -Uri "http://127.0.0.1:18766/api/dev/use-local-java" -Method POST -TimeoutSec 3
            if ($sw.ok) {
                Write-Host "==> Sync Helper hot-switched to local Java" -ForegroundColor Green
                return
            }
        } catch { }
    }
    Start-Sleep -Seconds 1
}
Write-Host "==> [WARN] Helper started but panel not confirmed — open http://127.0.0.1:18766" -ForegroundColor Yellow
