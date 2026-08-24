@echo off
REM CrossHub Helper — 生成 .exe 应用程序
REM 这个脚本会将 Python 应用打包成独立的 Windows .exe 文件

setlocal enabledelayedexpansion

title CrossHub Helper - 应用打包工具

cls
echo.
echo ============================================================
echo  CrossHub Helper - Windows 应用程序生成
echo ============================================================
echo.

set SCRIPT_DIR=%~dp0
set LAUNCHER=%SCRIPT_DIR%CrossHubHelper_launcher.py
set BUILD_DIR=%SCRIPT_DIR%build
set DIST_DIR=%SCRIPT_DIR%dist

REM 检查 PyInstaller
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller 未安装
    echo.
    echo 正在安装 PyInstaller...
    pip install pyinstaller -q
)

REM 检查启动器文件
if not exist "%LAUNCHER%" (
    echo [ERROR] 找不到启动器: %LAUNCHER%
    pause
    exit /b 1
)

echo [*] 准备打包...
echo  - 启动器: %LAUNCHER%
echo  - 输出目录: %DIST_DIR%
echo.

REM 清理旧的构建
echo [*] 清理旧的构建文件...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%" >nul 2>&1
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%" >nul 2>&1

echo.
echo [*] 正在编译应用程序（这可能需要 1-2 分钟）...
echo.

REM 使用 PyInstaller 生成 .exe
REM 参数说明:
REM  -F: 生成单个 .exe 文件
REM  -w: 无控制台窗口（Windows GUI 模式）
REM  -n: 应用名称
REM  -i: 图标文件
REM  --paths: Python 搜索路径

python -m PyInstaller ^
    -F ^
    -w ^
    -n "CrossHub Helper" ^
    --add-data "backend/python:backend/python" ^
    --add-data "backend/python/agent/panel:backend/python/agent/panel" ^
    --paths "%SCRIPT_DIR%backend/python" ^
    --hidden-import=flask ^
    --hidden-import=webview ^
    --hidden-import=pystray ^
    --hidden-import=PIL ^
    --hidden-import=httpx ^
    "%LAUNCHER%"

if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] 编译失败！
    echo.
    pause
    exit /b 1
)

color 0A
echo.
echo [✓] 编译成功！
echo.
echo 应用程序已生成:
echo  %DIST_DIR%\CrossHub Helper.exe
echo.
echo ============================================================
echo  使用方法
echo ============================================================
echo.
echo 1. 双击 CrossHub Helper.exe 即可启动应用
echo 2. 右键创建快捷方式放在桌面
echo 3. 或直接将 .exe 放入 Windows 启动文件夹自动启动
echo.
echo 启动文件夹位置:
echo  %%APPDATA%%\Microsoft\Windows\Start Menu\Programs\Startup
echo.

echo [*] 是否立即创建桌面快捷方式? (Y/N)
set /p CREATE_SHORTCUT="请选择 (Y/N): "

if /i "%CREATE_SHORTCUT%"=="Y" (
    echo.
    echo [*] 创建快捷方式...

    for /f "tokens=3" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop ^| find "Desktop"') do (
        set DESKTOP=%%A
    )

    if not "!DESKTOP!"=="" (
        powershell -Command "^
            $shell = New-Object -ComObject WScript.Shell; ^
            $link = $shell.CreateShortCut('!DESKTOP!\CrossHub Helper.lnk'); ^
            $link.TargetPath = '%DIST_DIR%\CrossHub Helper.exe'; ^
            $link.WorkingDirectory = '%SCRIPT_DIR%'; ^
            $link.Description = 'CrossHub 同步助手'; ^
            $link.IconLocation = 'C:\Windows\System32\shell32.dll,49'; ^
            $link.Save(); ^
            Write-Host 'OK'
        " >nul 2>&1

        if !errorlevel! equ 0 (
            echo [✓] 快捷方式已创建: !DESKTOP!\CrossHub Helper.lnk
        )
    )
)

echo.
echo [✓] 打包完成！
echo.
pause
