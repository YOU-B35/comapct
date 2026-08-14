# 用「桌面版 Sync Helper.exe」做本地联调（强制允许本机 Java）
# 推荐：日常本地开发直接 powershell -File scripts\start-local.ps1
#       （已自动调用 ensure-local-helper.ps1，无需每次手改）
# 本脚本保留给只想单独重启助手的场景。
#
# 用法: powershell -File scripts\start-desktop-helper-local.ps1

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "ensure-local-helper.ps1")
