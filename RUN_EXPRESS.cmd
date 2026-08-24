@echo off
cd /d "%~dp0"

set PATH=%CD%\tools\node;%PATH%
set PORT=3000

cd script\api-server

echo.
echo ╔════════════════════════════════════════╗
echo ║    CrossHub - Express API (:3000)    ║
echo ╚════════════════════════════════════════╝
echo.
echo 正在安装依赖...
npm install

echo.
echo 启动 Express...
npm start

pause
