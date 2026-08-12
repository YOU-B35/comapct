# Enable portable JDK/Maven in current PowerShell session
$Root = Split-Path -Parent $PSScriptRoot
$env:JAVA_HOME = Join-Path $Root "tools\jdk-17"
$env:Path = "$env:JAVA_HOME\bin;" + (Join-Path $Root "tools\maven\bin") + ";" + $env:Path
Write-Host "JAVA_HOME=$env:JAVA_HOME"
java -version
mvn -version

# Optional Commander BFF credentials (gitignored)
$commanderEnv = Join-Path $Root "backend\java\.commander.env"
if (Test-Path $commanderEnv) {
    Get-Content $commanderEnv | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if ($key) {
            Set-Item -Path "Env:$key" -Value $val
        }
    }
    Write-Host "Loaded $commanderEnv"
}
