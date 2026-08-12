# 本地启动：Java(18080) + Express(3000) + Vue(5173)
# 用法: powershell -File scripts\start-local.ps1
# 会先关闭上一轮 launcher 窗口，再启动（避免堆几十个 PowerShell）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_launcher-utils.ps1")

$env:NODE_HOME = if ($env:NODE_HOME) { $env:NODE_HOME } else { "D:\dev\env\tools\node" }
$env:PATH = "$env:NODE_HOME;$env:PATH"

Write-Host "==> close previous launcher windows" -ForegroundColor Cyan
Stop-CrosshubLauncherWindows

Write-Host "==> stop old listeners on 5173 / 18080 / 3000" -ForegroundColor Cyan
@(5173, 18080, 3000) | ForEach-Object { Stop-ListenerPort -Port $_ }
Start-Sleep -Seconds 1

Write-Host "==> start Java API :18080" -ForegroundColor Cyan
$javaLauncher = Join-Path $env:TEMP "crosshub-java.ps1"
Start-CrosshubLauncherWindow -Name "java" -LauncherPath $javaLauncher -ScriptLines @(
    ". '$Root\scripts\env-java.ps1'"
    "Set-Location '$Root\backend\java'"
    "`$env:SPRING_PROFILES_ACTIVE='dev'"
    "mvn -q spring-boot:run"
)

Write-Host "==> start Express :3000" -ForegroundColor Cyan
$expressLauncher = Join-Path $env:TEMP "crosshub-express.ps1"
Start-CrosshubLauncherWindow -Name "express" -LauncherPath $expressLauncher -ScriptLines @(
    "Set-Location '$Root\script\api-server'"
    "if (-not (Test-Path node_modules)) { npm install }"
    "`$env:PORT='3000'"
    "npm start"
)

Write-Host "==> start Vue dev :5174" -ForegroundColor Cyan
$webLauncher = Join-Path $env:TEMP "crosshub-web.ps1"
Start-CrosshubLauncherWindow -Name "web" -LauncherPath $webLauncher -ScriptLines @(
    "Set-Location '$Root\dev\vue-site'"
    "if (-not (Test-Path node_modules)) { npm install }"
    "npm run dev -- --port 5174 --strictPort"
)

Start-Sleep -Seconds 8
Write-Host ""
Write-Host "Local URLs:" -ForegroundColor Green
Write-Host "  Web     http://localhost:5174"
Write-Host "  Java    http://localhost:18080/api/temu/shops"
Write-Host "  Express http://localhost:3000/api/health"
