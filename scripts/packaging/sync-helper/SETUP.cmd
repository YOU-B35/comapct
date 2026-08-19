@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "EXE=%~dp0CrossHub-Sync-Helper.exe"
if not exist "%EXE%" (
  echo [错误] 未找到 CrossHub-Sync-Helper.exe
  echo 请确认本脚本与 exe 在同一目录（解压后的 CrossHub-Sync-Helper 文件夹内）。
  pause
  exit /b 1
)

echo [1/2] 注册「连接助手」协议...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register-protocol.ps1" -ExePath "%EXE%"
if errorlevel 1 (
  echo [警告] 协议注册失败，仍将尝试启动助手；网站「连接助手」可能无法自动拉起。
) else (
  echo       协议已注册：crosshub-sync-helper://
)

echo [2/2] 启动 Sync Helper...
start "" "%EXE%"
echo.
echo 已启动。请保持助手运行，回到网站：
echo   1. 点「生成绑定码」并在助手面板填入
echo   2. 状态栏显示助手在线后，再点「打开登录」
echo.
timeout /t 4 >nul
endlocal
