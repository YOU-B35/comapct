@echo off
REM CrossHub Helper — 创建桌面快捷方式
REM 将此脚本放在项目根目录运行

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0

REM 获取用户桌面路径
for /f "tokens=3" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop ^| find "Desktop"') do (
    set DESKTOP=%%A
)

if "!DESKTOP!"=="" (
    echo 无法获取桌面路径
    exit /b 1
)

REM 创建快捷方式
REM 使用 VBScript 创建快捷方式
set VBS_FILE=%TEMP%\create_shortcut_tmp.vbs

(
echo Set shell = CreateObject("WScript.Shell")
echo Set fso = CreateObject("Scripting.FileSystemObject"^)
echo.
echo sLinkFile = "%DESKTOP%\CrossHub Helper.lnk"
echo sBatFile = "%SCRIPT_DIR%START_HELPER.cmd"
echo.
echo If NOT fso.FileExists(sBatFile^) Then
echo   WScript.Echo "找不到: " ^& sBatFile
echo   WScript.Quit 1
echo End If
echo.
echo Set oLink = shell.CreateShortCut(sLinkFile^)
echo   oLink.TargetPath = sBatFile
echo   oLink.WorkingDirectory = "%SCRIPT_DIR%"
echo   oLink.Description = "CrossHub Sync Helper - 跨平台电商同步助手"
echo   oLink.IconLocation = "C:\Windows\System32\shell32.dll,49"
echo   oLink.Save
echo.
echo WScript.Echo "✓ 快捷方式已创建: " ^& sLinkFile
) > "%VBS_FILE%"

cscript.exe "%VBS_FILE%"
if %errorlevel% equ 0 (
    echo.
    echo ✓ 快捷方式创建成功
    echo   位置: %DESKTOP%\CrossHub Helper.lnk
    echo.
    echo 💡 下次只需双击桌面快捷方式即可启动 Helper
) else (
    echo.
    echo ✗ 快捷方式创建失败
)

del /q "%VBS_FILE%" 2>nul

pause
