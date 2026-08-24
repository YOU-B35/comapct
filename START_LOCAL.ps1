# CrossHub 本地启动脚本 (PowerShell)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot

# 配置 JDK 和 Maven
$env:JAVA_HOME = "$Root\tools\jdk-17"
$env:MAVEN_HOME = "$Root\tools\maven"
$env:PATH = "$env:JAVA_HOME\bin;$env:MAVEN_HOME\bin;$env:PATH"

Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   CrossHub 本地启动（5174 / 18080 / 3000）║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查环境
Write-Host "✓ JAVA_HOME: $env:JAVA_HOME" -ForegroundColor Green
Write-Host "✓ MAVEN_HOME: $env:MAVEN_HOME" -ForegroundColor Green
Write-Host ""

# 关闭之前的服务（可选）
Write-Host "🔄 停止旧服务..." -ForegroundColor Yellow
Get-Process java -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "npm|vite" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 启动 Java API (:18080)
Write-Host "[1/3] 启动 Java API (:18080)..." -ForegroundColor Cyan
$javaScript = @'
$env:SPRING_PROFILES_ACTIVE = "dev"
$env:JAVA_TOOL_OPTIONS = "-Duser.timezone=Asia/Shanghai"
Set-Location "{0}\backend\java"
Write-Host ">>> mvn spring-boot:run" -ForegroundColor Yellow
& mvn spring-boot:run
'@ -f $Root

$javaProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $javaScript -PassThru -WindowStyle Normal
Write-Host "   ✓ Java 进程 PID: $($javaProcess.Id)" -ForegroundColor Green
Start-Sleep -Seconds 3

# 启动 Express (:3000)
Write-Host "[2/3] 启动 Express (:3000)..." -ForegroundColor Cyan
$expressScript = @'
Set-Location "{0}\script\api-server"
if (-not (Test-Path node_modules)) {
    Write-Host ">>> npm install" -ForegroundColor Yellow
    & npm install
}
$env:PORT = "3000"
Write-Host ">>> npm start" -ForegroundColor Yellow
& npm start
'@ -f $Root

$expressProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $expressScript -PassThru -WindowStyle Normal
Write-Host "   ✓ Express 进程 PID: $($expressProcess.Id)" -ForegroundColor Green
Start-Sleep -Seconds 2

# 启动 Vue (:5174)
Write-Host "[3/3] 启动 Vue 前端 (:5174)..." -ForegroundColor Cyan
$vueScript = @'
Set-Location "{0}\dev\vue-site"
if (-not (Test-Path node_modules)) {
    Write-Host ">>> npm install" -ForegroundColor Yellow
    & npm install
}
Write-Host ">>> npm run dev -- --port 5174 --strictPort" -ForegroundColor Yellow
& npm run dev -- --port 5174 --strictPort
'@ -f $Root

$vueProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $vueScript -PassThru -WindowStyle Normal
Write-Host "   ✓ Vue 进程 PID: $($vueProcess.Id)" -ForegroundColor Green

Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║        所有服务已启动！              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📍 访问地址：" -ForegroundColor Green
Write-Host "   Web:     http://localhost:5174" -ForegroundColor Cyan
Write-Host "   Java:    http://localhost:18080/api/temu/shops" -ForegroundColor Cyan
Write-Host "   Express: http://localhost:3000/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔐 登录账号：" -ForegroundColor Green
Write-Host "   admin@crosshub.cn / 12345678" -ForegroundColor Yellow
Write-Host ""
Write-Host "⏳ 等待 30-60 秒让 Java 完全启动..." -ForegroundColor Yellow
Write-Host ""

# 监视进程
$timeout = 0
while ($timeout -lt 120) {
    if (-not (Get-Process -Id $javaProcess.Id -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Java 进程已停止！" -ForegroundColor Red
        break
    }
    Start-Sleep -Seconds 5
    $timeout += 5
}
