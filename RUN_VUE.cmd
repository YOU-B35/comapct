@echo off
cd /d "%~dp0"

set PATH=%CD%\tools\node;%PATH%

cd dev\vue-site

echo.
echo ╔════════════════════════════════════════╗
echo ║    CrossHub - Vue Frontend (:5174)   ║
echo ╚════════════════════════════════════════╝
echo.
echo 正在启动 Vue...
npm run dev -- --port 5174 --strictPort

pause
