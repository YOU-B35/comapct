@echo off
REM 快速测试启动脚本 - 用于验证改进是否有效

color 0A
cls

echo.
echo ============================================================
echo  CrossHub Helper — 无窗口启动测试
echo ============================================================
echo.

set SCRIPT_DIR=%~dp0
set PYTHON_SCRIPT=%SCRIPT_DIR%backend\python\agent\desktop_app.py
set LOG_FILE=%SCRIPT_DIR%logs\sync_helper_desktop.log

REM 检查文件
if not exist "%PYTHON_SCRIPT%" (
    color 0C
    echo [ERROR] 找不到启动脚本: %PYTHON_SCRIPT%
    echo.
    echo 请确保项目结构完整
    echo.
    pause
    exit /b 1
)

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo [ERROR] Python 未在 PATH 中
    echo.
    echo 请先安装 Python 3.10+
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

color 0A
echo [✓] 环境检查通过
echo.
echo 正在启动 CrossHub Helper (无窗口模式)...
echo.

REM 创建日志目录
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

REM 启动应用（隐藏窗口）
start "" /b pythonw "%PYTHON_SCRIPT%"

if errorlevel 1 (
    start "" /b python "%PYTHON_SCRIPT%"
)

echo.
echo [✓] 应用已在后台启动
echo.
echo 📊 应该在 1-2 秒后看到桌面窗口打开
echo 📝 日志文件: %LOG_FILE%
echo.

REM 等待窗口启动
timeout /t 2 /nobreak

REM 检查日志文件是否生成
if exist "%LOG_FILE%" (
    echo.
    color 0B
    echo [✓] 日志文件成功生成！
    echo.
    echo 最近 10 行日志:
    echo ============================================================
    color 0A
    for /f "tokens=*" %%a in ('powershell -Command "Get-Content '%LOG_FILE%' -Tail 10"') do (
        echo  %%a
    )
    color 0B
    echo ============================================================
    echo.
) else (
    echo.
    color 0E
    echo [!] 日志文件未生成（可能是首次运行，或应用尚未完全启动）
    echo.
)

echo.
color 0A
echo 💡 故障排除:
echo  1. 如果窗口未打开: 检查日志文件 %LOG_FILE%
echo  2. 如果显示控制台: 确保使用 pythonw 而非 python
echo  3. 如果网络超时: 检查 Java API 连接状态
echo.

echo 按任意键关闭此窗口...
pause >nul
color 07
