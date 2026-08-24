@echo off
REM CrossHub Helper — 应用启动器
REM 直接双击此文件即可启动应用（无 Python 窗口显示）

cd /d "%~dp0"

REM 隐藏的启动
start "" /min pythonw.exe backend\python\agent\desktop_app.py

exit /b 0
