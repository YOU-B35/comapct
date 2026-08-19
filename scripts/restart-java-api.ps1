# 编译并重启 Java API（:18080）；先关旧 launcher 窗口，不堆新 PowerShell
# 用法: powershell -File scripts\restart-java-api.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_launcher-utils.ps1")

Write-Host "==> compile Java API" -ForegroundColor Cyan
. (Join-Path $PSScriptRoot "env-java.ps1")
Set-Location (Join-Path $Root "backend\java")
mvn -q compile -DskipTests

Write-Host "==> stop old Java launcher / port 18080" -ForegroundColor Cyan
Stop-CrosshubLauncherWindows -Names @("java")
Stop-ListenerPort -Port 18080
Start-Sleep -Seconds 1

Write-Host "==> start Java API :18080" -ForegroundColor Cyan
$javaLauncher = Join-Path $env:TEMP "crosshub-java.ps1"
Start-CrosshubLauncherWindow -Name "java" -LauncherPath $javaLauncher -ScriptLines @(
    ". '$Root\scripts\env-java.ps1'"
    "Set-Location '$Root\backend\java'"
    "`$env:SPRING_PROFILES_ACTIVE='dev'"
    # Pin main DB — avoid inheriting a worktree CROSSHUB_DB_PATH from the parent shell
    "`$env:CROSSHUB_DB_PATH='$Root\backend\data\crosshub.db'"
    "mvn -q -DskipTests spring-boot:run"
)

Start-Sleep -Seconds 12
$listening = Get-NetTCPConnection -LocalPort 18080 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "Java API ready: http://localhost:18080" -ForegroundColor Green
} else {
    Write-Host "Java API not listening on 18080 yet — check the Java launcher window" -ForegroundColor Yellow
}
