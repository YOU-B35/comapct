@echo off
REM CrossHub Sync Helper — Windows 批处理启动脚本
REM 用途: 后台启动应用，不显示 Python 控制台窗口
REM
REM 使用方法: 直接双击此文件即可启动
REM 注意: 仅在 Windows 7+ 系统上生效

setlocal enabledelayedexpansion

REM 设置窗口标题
title CrossHub Sync Helper - 正在启动...

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%backend\python\agent\desktop_app.py

REM 检查 Python 脚本是否存在
if not exist "%PYTHON_SCRIPT%" (
    powershell -Command "Add-Type –AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('找不到启动文件: %PYTHON_SCRIPT%', 'CrossHub Helper — 启动失败', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)" > nul 2>&1
    exit /b 1
)

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    powershell -Command "Add-Type –AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Python 未在系统 PATH 中。`n`n请先安装 Python 3.10+ 或配置系统环境变量。', 'CrossHub Helper — 启动失败', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)" > nul 2>&1
    exit /b 1
)

REM 创建日志目录
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

REM 使用 pythonw 启动（不显示控制台窗口）
REM 第一个参数: 脚本路径
REM /B 参数: 创建新的命令处理程序时不创建新窗口
REM /I 参数: 继承父进程的环境变量

echo 🚀 启动 CrossHub Sync Helper...
echo.
echo Python 脚本: %PYTHON_SCRIPT%
echo 日志目录: %SCRIPT_DIR%logs
echo.

REM 检查是否已有进程运行
tasklist /fi "imagename eq pythonw.exe" | find /i "python" > nul
if errorlevel 1 (
    echo 启动新进程...
) else (
    echo ⚠ 检测到已有 Python 进程运行，可能是 Helper 已启动
)

REM 使用 start 命令以隐藏窗口方式启动
REM /min 最小化窗口
REM /separate 在单独的内存空间中启动
start "" /b pythonw "%PYTHON_SCRIPT%"

if errorlevel 1 (
    REM 如果 pythonw 失败，尝试用 python
    start "" /b python "%PYTHON_SCRIPT%"
)

echo.
echo ✓ CrossHub Helper 已在后台启动
echo.
echo 💡 提示:
echo   • 桌面窗口将在 1-2 秒后自动打开
echo   • 如果未出现，请检查: %SCRIPT_DIR%logs\sync_helper.log
echo   • 启动后可以关闭此窗口，应用将继续后台运行
echo.
echo 按任意键关闭此窗口...

timeout /t 3 /nobreak
exit /b 0
