# Build CrossHub-Sync-Helper.exe (运维机安装；不对运营前端暴露)
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
    --hidden-import agent.config `
    --hidden-import agent.health_server `
    --hidden-import agent.tray_app `
    --hidden-import flask `
    --hidden-import pystray `
    --hidden-import PIL `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageDraw `
    --add-data "$PyRoot\agent\panel;agent/panel" `
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
CrossHub Sync Helper（运维机专用）
================================

1. 编辑本目录 config.json：
   - agent_token：由 Java /api/agent/setup 生成（运维内部完成，不在运营前端下载）
   - java_api_url：API 根地址（默认已写入）

2. 双击 CrossHub-Sync-Helper.exe，保持窗口打开。

3. 服务端每天 09:30 下发全平台日批；本程序在本机开浏览器执行 Temu/Amazon 等任务。

4. 需要本机已安装 Google Chrome；Amazon 另需紫鸟（可选自动拉起）。

5. 开机自启（推荐）：在仓库根目录执行
   powershell -File scripts\install-sync-helper-autostart.ps1 -StartNow
   详见 docs/superpowers/specs/attachments/2026-07-29-rc-auto-checklist.md

不要把本程序的下载入口放到运营人员使用的网页上。
"@
Set-Content -Path (Join-Path $AppDir "README.txt") -Value $readme -Encoding UTF8

Write-Host "==> done: $AppDir" -ForegroundColor Green
Write-Host "    Edit config.json (agent_token) then run CrossHub-Sync-Helper.exe" -ForegroundColor Green
