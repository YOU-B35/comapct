# 首次配置 Temu 卖家后台登录（按租户隔离浏览器 Profile）
# 用法: powershell -File scripts\setup-temu-login.ps1 -TenantId 5
param(
    [Parameter(Mandatory = $true)]
    [int]$TenantId
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "backend\python")

Write-Host "==> Temu 登录配置（租户 $TenantId）" -ForegroundColor Cyan
Write-Host "将打开浏览器，请完成 Temu 卖家后台登录，并在浏览器里选好店铺。" -ForegroundColor Yellow
Write-Host "完成后回到终端按 Enter。" -ForegroundColor Yellow
Write-Host ""

py login.py --tenant-id $TenantId
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==> 验证爬虫" -ForegroundColor Cyan
py crawl.py --tenant-id $TenantId --json
exit $LASTEXITCODE
