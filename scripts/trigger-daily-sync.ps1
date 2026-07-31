# Manual sync enqueue (Helper only polls tasks; trigger via API)
#   powershell -File scripts/trigger-daily-sync.ps1 -Force
#   powershell -File scripts/trigger-daily-sync.ps1 -Platform amazon -Force
#   powershell -File scripts/trigger-daily-sync.ps1 -Platform temu -Force

param(
    [string]$ApiBase = "https://www.yoto.work",
    [string]$Account = "HangZhouYiTuo",
    [string]$Password = "HangZhouYiTuo",
    [ValidateSet("all", "amazon", "temu", "aliexpress")]
    [string]$Platform = "all",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ApiBase = $ApiBase.TrimEnd("/")
$forceQ = if ($Force) { "true" } else { "false" }

Write-Host ("==> login {0} @ {1}" -f $Account, $ApiBase) -ForegroundColor Cyan
$loginBody = @{ account = $Account; password = $Password } | ConvertTo-Json
$login = Invoke-RestMethod -Uri ($ApiBase + "/api/auth/login") -Method POST -ContentType "application/json" -Body $loginBody
$token = $login.data.token
if (-not $token) { throw "login failed: no token" }
$headers = @{ Authorization = ("Bearer " + $token) }

if ($Platform -eq "amazon") {
    $url = $ApiBase + "/api/amazon/sync"
    $body = @{ scope = "account_health"; force = [bool]$Force } | ConvertTo-Json
    Write-Host ("==> POST {0}" -f $url) -ForegroundColor Cyan
    $res = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -ContentType "application/json" -Body $body
}
elseif ($Platform -eq "temu") {
    $url = $ApiBase + "/api/temu/crawl"
    $body = @{ force = [bool]$Force } | ConvertTo-Json
    Write-Host ("==> POST {0}" -f $url) -ForegroundColor Cyan
    $res = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -ContentType "application/json" -Body $body
}
else {
    # all / aliexpress: full daily enqueue
    $url = $ApiBase + "/api/platform/daily-sync/run?force=" + $forceQ + [char]38 + "scope=tenant"
    Write-Host ("==> POST {0}" -f $url) -ForegroundColor Cyan
    $res = Invoke-RestMethod -Uri $url -Method POST -Headers $headers
}

$res | ConvertTo-Json -Depth 8
Write-Host ""
Write-Host "Keep Helper open; it polls tasks every ~10s. Health: http://127.0.0.1:18765/health" -ForegroundColor DarkCyan
