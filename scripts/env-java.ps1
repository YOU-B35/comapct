# Enable portable JDK/Maven in current PowerShell session
$Root = Split-Path -Parent $PSScriptRoot
$env:JAVA_HOME = Join-Path $Root "tools\jdk-17"
$env:Path = "$env:JAVA_HOME\bin;" + (Join-Path $Root "tools\maven\bin") + ";" + $env:Path
Write-Host "JAVA_HOME=$env:JAVA_HOME"
java -version
mvn -version
