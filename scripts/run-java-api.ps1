# 启动 Java Temu API（需先 setup-java.ps1）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $Root "scripts\env-java.ps1")
Set-Location (Join-Path $Root "backend\java")
$env:JAVA_TOOL_OPTIONS = '-Duser.timezone=Asia/Shanghai'
mvn spring-boot:run
