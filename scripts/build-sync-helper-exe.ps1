# Build CrossHub-Sync-Helper.exe (user-local Sync Helper package)
# Usage:
#   powershell -File scripts/build-sync-helper-exe.ps1
# Optional:
#   powershell -File scripts/build-sync-helper-exe.ps1 -JavaApiUrl "https://www.yoto.work"

param(
    [string]$JavaApiUrl = "https://www.yoto.work",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PyRoot = Join-Path $Root "backend\python"
$Entry = Join-Path $PyRoot "scripts\sync_helper_app.py"
$DistRoot = if ($OutDir) { $OutDir } else { Join-Path $Root "dist\CrossHub-Sync-Helper" }
$WorkDir = Join-Path $Root "dist\_pyinstaller_sync_helper"

if (-not (Test-Path $Entry)) {
    Write-Host "Entry not found: $Entry" -ForegroundColor Red
    exit 2
}

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python launcher 'py' not found." -ForegroundColor Red
    exit 3
}

Write-Host "==> ensure PyInstaller + tray deps" -ForegroundColor Cyan
& py -m pip install --quiet --upgrade pip pyinstaller pystray pillow flask | Out-Null

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

Write-Host "==> pyinstaller onedir" -ForegroundColor Cyan
& py -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "CrossHub-Sync-Helper" `
    --distpath $DistRoot `
    --workpath (Join-Path $WorkDir "build") `
    --specpath (Join-Path $WorkDir "spec") `
    --paths $PyRoot `
    --hidden-import agent `
    --hidden-import agent.main `
    --hidden-import agent.handlers `
    --hidden-import agent.temu_tasks `
    --hidden-import agent.java_client `
      --hidden-import agent.helper_java_url `
      --hidden-import agent.bind `
      --hidden-import agent.protocol_launch `
    --hidden-import flask `
    --hidden-import pystray `
    --hidden-import PIL `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageDraw `
    --add-data "$PyRoot\agent\panel;agent/panel" `
    --add-data "$PyRoot\agent\alibaba1688_product_tasks_legacy.bin;agent" `
    --hidden-import app.browser.context `
    --hidden-import app.crawler.temu_crawler `
    --hidden-import app.amazon.report_crawler `
    --hidden-import playwright `
    --collect-submodules agent `
    --collect-submodules app `
    --collect-all playwright `
    $Entry

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller failed" -ForegroundColor Red
    exit $LASTEXITCODE
}

# PyInstaller puts CrossHub-Sync-Helper/ under distpath when --name matches
$AppDir = Join-Path $DistRoot "CrossHub-Sync-Helper"
if (-not (Test-Path (Join-Path $AppDir "CrossHub-Sync-Helper.exe"))) {
    # sometimes flat
    $AppDir = $DistRoot
}

$example = Join-Path $Root "scripts\packaging\sync-helper\config.example.json"
$cfgOut = Join-Path $AppDir "config.example.json"
Copy-Item -Force $example $cfgOut
$cfgLive = Join-Path $AppDir "config.json"
if (-not (Test-Path $cfgLive)) {
    $obj = Get-Content $example -Raw -Encoding UTF8 | ConvertFrom-Json
    $obj.java_api_url = $JavaApiUrl
    ($obj | ConvertTo-Json -Depth 5) | Set-Content -Path $cfgLive -Encoding UTF8
}

$readme = @"
CrossHub Sync Helper（用户本机）
================================

【首次使用 — 必做】
1. 解压本文件夹到任意目录（建议桌面）。
2. 双击 SETUP.cmd（推荐），或双击 CrossHub-Sync-Helper.exe。
   SETUP.cmd 会注册「连接助手」协议并启动助手。
3. 保持程序运行（可最小化到托盘）。
4. 打开本机面板：http://127.0.0.1:18766
5. 在网站点「生成绑定码」，粘贴到助手面板完成绑定。
6. 网站状态栏显示「助手在线」后，再点「打开登录」。

【日常使用】
- 先确保本机助手已启动（SETUP.cmd 或 exe）。
- 网站可点「连接助手」自动拉起（需完成过首次 SETUP）。
- java_api_url 默认 https://www.yoto.work（一般无需修改）。
- 默认使用 Playwright 内置 Chromium（本机执行过一次 py -m playwright install chromium 即可）；未安装时自动回退本机 Google Chrome/Edge。

协议手动注册（若 SETUP 失败）：
  powershell -ExecutionPolicy Bypass -File .\register-protocol.ps1 -ExePath .\CrossHub-Sync-Helper.exe
"@
Set-Content -Path (Join-Path $AppDir "README.txt") -Value $readme -Encoding UTF8

Copy-Item -Force (Join-Path $Root "scripts\packaging\sync-helper\register-protocol.ps1") (Join-Path $AppDir "register-protocol.ps1")
Copy-Item -Force (Join-Path $Root "scripts\packaging\sync-helper\SETUP.cmd") (Join-Path $AppDir "SETUP.cmd")

Write-Host "==> done: $AppDir" -ForegroundColor Green
Write-Host "    Edit config.json (agent_token) then run CrossHub-Sync-Helper.exe" -ForegroundColor Green
