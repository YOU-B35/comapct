# 本地 Sync Helper 联调启动（不影响生产配置）
#
# 用法:
#   powershell -File scripts\run-sync-helper-local.ps1
#
# 原理:
#   - 使用独立配置文件 backend\python\.sync-helper-local\config.json
#     （不会改仓库根目录 / %LOCALAPPDATA%\CrossHub\SyncHelper 的生产配置）
#   - JAVA_API_URL=http://127.0.0.1:18080
#   - CROSSHUB_ALLOW_LOCAL_JAVA=1（否则助手会强制改回 https://www.yoto.work）
#
# 前提:
#   1. 本地 Java 已在 :18080 运行（scripts\restart-java-api.ps1）
#   2. 前端 npm run dev，登录本地后端（HangZhouYiTuo）
#   3. 在网页「Agent 节点 / 助手」重新生成绑定码，立刻粘贴到本地面板
#
# 测完恢复生产:
#   关掉本窗口；日常仍用线上助手 / 默认 config（勿设 CROSSHUB_ALLOW_LOCAL_JAVA）

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PyRoot = Join-Path $Root "backend\python"
$LocalDir = Join-Path $PyRoot ".sync-helper-local"
$LocalConfig = Join-Path $LocalDir "config.json"
$Entry = Join-Path $PyRoot "scripts\sync_helper_app.py"

if (-not (Test-Path $Entry)) {
    Write-Host "找不到 $Entry" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
if (-not (Test-Path $LocalConfig)) {
    @{
        java_api_url = "http://127.0.0.1:18080"
        display_name = "本机助手-本地联调"
    } | ConvertTo-Json | Set-Content -Path $LocalConfig -Encoding UTF8
    Write-Host "==> 已创建本地配置: $LocalConfig" -ForegroundColor Green
}

# 探测本机 Java
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:18080/api/health" -TimeoutSec 3
    Write-Host "==> 本机 Java :18080 OK ($($health.message))" -ForegroundColor Green
} catch {
    Write-Host "==> 本机 Java :18080 未就绪。请先: powershell -File scripts\restart-java-api.ps1" -ForegroundColor Yellow
}

$env:PYTHONPATH = $PyRoot
$env:JAVA_API_URL = "http://127.0.0.1:18080"
$env:CROSSHUB_ALLOW_LOCAL_JAVA = "1"
$env:CROSSHUB_HELPER_CONFIG = $LocalConfig
# 避免误用生产 token
Remove-Item Env:AGENT_TOKEN -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==== 本地助手联调 ====" -ForegroundColor Cyan
Write-Host "  JAVA_API_URL              = $env:JAVA_API_URL"
Write-Host "  CROSSHUB_ALLOW_LOCAL_JAVA = $env:CROSSHUB_ALLOW_LOCAL_JAVA"
Write-Host "  CROSSHUB_HELPER_CONFIG    = $env:CROSSHUB_HELPER_CONFIG"
Write-Host ""
Write-Host "步骤:" -ForegroundColor Cyan
Write-Host "  1. 浏览器打开 http://localhost:5173 ，用本地账号登录"
Write-Host "  2. 打开「设置 → Agent 节点」，生成绑定码（必须是本地 Java 生成的）"
Write-Host "  3. 在助手面板粘贴绑定码"
Write-Host "  4. 测完关闭本窗口即可；生产助手配置未被修改"
Write-Host ""

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "未找到 py 启动器，请安装 Python 3" -ForegroundColor Red
    exit 2
}

Set-Location $Root
& py -u $Entry
