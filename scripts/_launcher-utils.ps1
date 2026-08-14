# 本地服务 launcher 工具：复用/关闭旧 PowerShell 窗口，避免多轮重启堆几十个窗口
$script:CrosshubPidFile = Join-Path $env:TEMP "crosshub-launcher-pids.json"

$script:CrosshubLauncherMarkers = @{
    java    = "crosshub-java.ps1"
    express = "crosshub-express.ps1"
    web     = "crosshub-web.ps1"
    worker  = "crosshub-worker.ps1"
    collector = "crosshub-collector.ps1"
    helper  = "crosshub-helper.ps1"
}

function Get-CrosshubLauncherPids {
    if (-not (Test-Path $script:CrosshubPidFile)) {
        return @{}
    }
    try {
        $raw = Get-Content $script:CrosshubPidFile -Raw -Encoding UTF8
        if (-not $raw) { return @{} }
        $obj = $raw | ConvertFrom-Json
        $map = @{}
        foreach ($prop in $obj.PSObject.Properties) {
            $map[$prop.Name] = [int]$prop.Value
        }
        return $map
    } catch {
        return @{}
    }
}

function Save-CrosshubLauncherPid {
    param([string]$Name, [int]$ProcessId)
    $map = Get-CrosshubLauncherPids
    $map[$Name] = $ProcessId
    $map | ConvertTo-Json | Set-Content -Path $script:CrosshubPidFile -Encoding UTF8
}

function Stop-CrosshubLauncherWindows {
    param([string[]]$Names)

    $targets = if ($Names -and $Names.Count -gt 0) { $Names } else { @($script:CrosshubLauncherMarkers.Keys) }
    $markers = @()
    foreach ($name in $targets) {
        if ($script:CrosshubLauncherMarkers[$name]) {
            $markers += $script:CrosshubLauncherMarkers[$name]
        }
    }

    $stopped = @{}

    foreach ($name in $targets) {
        $map = Get-CrosshubLauncherPids
        $launcherPid = $map[$name]
        if (-not $launcherPid) { continue }
        $proc = Get-Process -Id $launcherPid -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match '^(powershell|pwsh)$') {
            Write-Host "  close launcher window [$name] PID $launcherPid" -ForegroundColor Yellow
            Stop-Process -Id $launcherPid -Force -ErrorAction SilentlyContinue
            $stopped[$launcherPid] = $true
        }
    }

    $pattern = ($markers | ForEach-Object { [regex]::Escape($_) }) -join '|'
    if ($pattern) {
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(powershell|pwsh)\.exe$' -and $_.CommandLine -match $pattern } |
            ForEach-Object {
                if ($stopped.ContainsKey($_.ProcessId)) { return }
                Write-Host "  close orphan launcher PID $($_.ProcessId)" -ForegroundColor Yellow
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
    }
}

function Stop-ListenerPort {
    param([int]$Port)

    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "  stop port $Port : $($p.ProcessName) (PID $($p.Id))" -ForegroundColor Yellow
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            }
        }
}

function Start-CrosshubLauncherWindow {
    param(
        [string]$Name,
        [string]$LauncherPath,
        [string[]]$ScriptLines
    )

    $ScriptLines | Set-Content -Path $LauncherPath -Encoding UTF8
    $proc = Start-Process powershell -WindowStyle Normal -PassThru `
        -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $LauncherPath)
    Save-CrosshubLauncherPid -Name $Name -ProcessId $proc.Id
    return $proc
}
