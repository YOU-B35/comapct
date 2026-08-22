# 编译并重启 Java(:18080) + Vue(:5173)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_launcher-utils.ps1")
$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'

$env:NODE_HOME = if ($env:NODE_HOME) { $env:NODE_HOME } else { "D:\dev\env\tools\node" }
$env:PATH = "$env:NODE_HOME;$env:PATH"

Write-Host "==> compile Java API" -ForegroundColor Cyan
Set-Location (Join-Path $Root "backend\java")
mvn -q compile -DskipTests

Write-Host "==> compile Vue frontend" -ForegroundColor Cyan
Set-Location (Join-Path $Root "dev\vue-site")
npm run build

Write-Host "==> stop old Java / Vue / worker / collector launchers and ports" -ForegroundColor Cyan
Stop-CrosshubLauncherWindows -Names @("java", "web", "worker", "collector")
Stop-ListenerPort -Port 18080
Stop-ListenerPort -Port 5173
Stop-ListenerPort -Port 18082
Start-Sleep -Seconds 1

Write-Host "==> start Java API :18080" -ForegroundColor Cyan
$javaLauncher = Join-Path $env:TEMP "crosshub-java.ps1"
Start-CrosshubLauncherWindow -Name "java" -LauncherPath $javaLauncher -ScriptLines @(
    ". '$Root\scripts\env-java.ps1'"
    "Set-Location '$Root\backend\java'"
    "`$env:SPRING_PROFILES_ACTIVE='dev'"
    "`$env:JAVA_TOOL_OPTIONS='-Duser.timezone=Asia/Shanghai'"
    "mvn -q spring-boot:run"
)

Write-Host "==> wait for Java API :18080" -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(45)
$javaUp = $false
while ((Get-Date) -lt $deadline) {
    $javaUp = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue
    if ($javaUp) { break }
    Start-Sleep -Seconds 2
}

Write-Host "==> start Vue dev :5174" -ForegroundColor Cyan
$webLauncher = Join-Path $env:TEMP "crosshub-web.ps1"
Start-CrosshubLauncherWindow -Name "web" -LauncherPath $webLauncher -ScriptLines @(
    "Set-Location '$Root\dev\vue-site'"
    "npm run dev -- --port 5174 --strictPort"
)

Write-Host "==> start Temu collector :18082" -ForegroundColor Cyan
$collectorLauncher = Join-Path $env:TEMP "crosshub-collector.ps1"
Start-CrosshubLauncherWindow -Name "collector" -LauncherPath $collectorLauncher -ScriptLines @(
    "Set-Location '$Root'"
    "python backend/python/temu_collector_service.py --host 127.0.0.1 --port 18082"
)

Write-Host "==> start monitor worker" -ForegroundColor Cyan
$workerLauncher = Join-Path $env:TEMP "crosshub-worker.ps1"
@(
    "Set-Location '$Root\backend\python'"
    "`$env:CROSSHUB_DB_PATH='$Root\backend\data\crosshub.db'"
    "`$env:CROSSHUB_MONITOR_EVIDENCE_DIR='$Root\backend\python\exports\ctf-website'"
    "`$env:CROSSHUB_TEMU_COLLECTOR_URL='http://127.0.0.1:18082'"
    "while (`$true) {"
    "  try {"
    "    python monitor_worker.py --once --json"
    "  } catch {"
    "    Write-Host `"monitor worker loop error: `$($_.Exception.Message)`" -ForegroundColor Yellow"
    "  }"
    "  Start-Sleep -Seconds 5"
    "}"
) | Set-Content -Path $workerLauncher -Encoding UTF8
$workerProc = Start-Process powershell -WindowStyle Hidden -PassThru `
    -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $workerLauncher)
Save-CrosshubLauncherPid -Name "worker" -ProcessId $workerProc.Id

Start-Sleep -Seconds 12
$javaUp = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue
$webUp = Get-NetTCPConnection -LocalPort 5174 -State Listen -ErrorAction SilentlyContinue
if ($javaUp) {
    Write-Host "Java API ready: http://localhost:18080" -ForegroundColor Green
} else {
    Write-Host "Java API not ready on 18080 — check Java launcher window" -ForegroundColor Yellow
}
if ($webUp) {
    Write-Host "Vue dev ready: http://localhost:5174" -ForegroundColor Green
} else {
    Write-Host "Vue dev not ready on 5174 — check Web launcher window" -ForegroundColor Yellow
}
