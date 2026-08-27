# 运维：写入 Sync Helper config.json（不经过运营前端）
param(
    [Parameter(Mandatory = $true)][string]$AgentToken,
    [string]$JavaApiUrl = "https://www.yoto.work",
    [string]$TargetDir = "",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $TargetDir) {
    $TargetDir = Join-Path $Root "dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper"
}
if (-not $ProjectRoot) {
    $ProjectRoot = $Root
}
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
$path = Join-Path $TargetDir "config.json"
# 无 BOM，避免 Python json 解析失败
$payload = @{
    agent_token = $AgentToken
    java_api_url = $JavaApiUrl.TrimEnd("/")
    health_port = 18765
    start_ziniao = $true
    project_root = $ProjectRoot
    temu_profile_root = (Join-Path $ProjectRoot "backend\python\.temu-browser-profile")
    ae_profile_root = (Join-Path $ProjectRoot "backend\python\.aliexpress-browser-profile")
    pdd_profile_root = (Join-Path $ProjectRoot "backend\python")
    a1688_profile_root = (Join-Path $ProjectRoot "backend\python\.1688-browser-profile")
} | ConvertTo-Json
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $payload, $utf8NoBom)
Write-Host "Wrote $path" -ForegroundColor Green
Write-Host "  java_api_url=$($JavaApiUrl.TrimEnd('/'))"
Write-Host "  project_root=$ProjectRoot"
