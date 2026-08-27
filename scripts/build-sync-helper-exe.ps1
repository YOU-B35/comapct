# Build CrossHub-Sync-Helper.exe (64-bit desktop app package)
# ------------------------------------------------------------------
# 产出：dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper.exe
#       * 真·64 位 Windows EXE（AMD64 / x64）
#       * 无控制台黑框（--windowed / console=False）
#       * 带应用图标 CrossHub.ico（16~256 多尺寸，任务栏/桌面/开始菜单都适配）
#       * 带版本资源（右键 → 属性 → 详细信息 → 文件描述 / 公司 / 版本号）
# 版本策略（用户明确要求）：
#   * 默认 onedir 模式 = 托盘浏览器版（入口 sync_helper_app.py），日常/生产使用；
#   * --onefile 模式 = 桌面窗口版（入口 sync_helper_desktop.py，pywebview），
#     默认禁用（含生产部署），仅当显式加 -AllowDesktop 才允许构建。
#
# 用法：
#   powershell -File scripts\build-sync-helper-exe.ps1
#   powershell -File scripts\build-sync-helper-exe.ps1 -JavaApiUrl "https://www.yoto.work"
#   powershell -File scripts\build-sync-helper-exe.ps1 -OneFile -AllowDesktop  # 仅用户明确授权时

param(
    [string]$JavaApiUrl = "",
    [string]$OutDir = "",
    [switch]$OneFile = $false,
    [switch]$AllowDesktop = $false
)

# Ensure UTF-8 output encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Continue"
# 致命错误手动 exit；native stderr 不直接当终止错误

# Windows PowerShell 5.1 不支持三元运算符，这里用兼容写法解析默认 API 地址
if (-not $JavaApiUrl) {
    $JavaApiUrl = [System.Environment]::GetEnvironmentVariable("JAVA_API_URL")
    if (-not $JavaApiUrl) {
        $JavaApiUrl = "https://www.yoto.work"
    }
}

# ============================================================
# 0) 64 位校验 —— 绝不允许 32 位 Python 产出假 x64 EXE
# ============================================================
$BitsCheck = & python -c "import sys,struct;print(struct.calcsize('P')*8, end='')" 2>$null
if (-not $BitsCheck) { $BitsCheck = "0" }
$PyExe    = & python -c "import sys;print(sys.executable, end='')" 2>$null
Write-Host "==> [ARCH] Python 解释器: $PyExe" -ForegroundColor Cyan
Write-Host "==> [ARCH] Python 位数     : $BitsCheck-bit" -ForegroundColor Cyan
if ([int]$BitsCheck -ne 64) {
    Write-Host "[FATAL] 当前 Python 是 $BitsCheck 位，打包出来的 EXE 会是 32 位。" -ForegroundColor Red
    Write-Host "        请先安装 64 位 Python 3.10+ x64 后再执行本脚本。" -ForegroundColor Red
    exit 10
}

# ⚠ 桌面窗口版默认禁用（含生产部署）：--onefile 构建的是桌面版（入口 sync_helper_desktop.py）。
# 只有用户显式加 -AllowDesktop 才允许构建；日常/生产一律使用 onedir 托盘浏览器版。
if ($OneFile -and -not $AllowDesktop) {
    Write-Host "[FATAL] --onefile 构建的是「桌面窗口版」（入口 sync_helper_desktop.py）。" -ForegroundColor Red
    Write-Host "        按用户要求，桌面版默认禁用（含生产部署）；如确需构建请显式加 -AllowDesktop 参数。" -ForegroundColor Red
    exit 30
}

$Root       = Split-Path -Parent $PSScriptRoot
$PyRoot     = Join-Path $Root "backend\python"
$Entry      = Join-Path $PyRoot "scripts\sync_helper_desktop.py"
$Assets     = Join-Path $Root "scripts\packaging\sync-helper"
$Icon       = Join-Path $Assets "CrossHub.ico"
$VersionRes = Join-Path $Assets "version_info.txt"
$SpecPath   = Join-Path $Root "dist\_pyinstaller_sync_helper\spec\CrossHub-Sync-Helper.spec"
$DistRoot   = if ($OutDir) { $OutDir } else { Join-Path $Root "dist\CrossHub-Sync-Helper" }
$WorkDir    = Join-Path $Root "dist\_pyinstaller_sync_helper"

if (-not (Test-Path $Entry))     { Write-Host "[FATAL] Entry not found: $Entry" -ForegroundColor Red; exit 2 }
if (-not (Test-Path $Icon))      { Write-Host "[FATAL] Icon not found:  $Icon"  -ForegroundColor Red; exit 2 }
if (-not (Test-Path $VersionRes)){ Write-Host "[FATAL] Version res not found: $VersionRes" -ForegroundColor Red; exit 2 }
if (-not (Test-Path $SpecPath))  { Write-Host "[FATAL] Spec not found: $SpecPath" -ForegroundColor Red; exit 2 }

# ============================================================
# 1) 依赖（PyInstaller / pystray / pillow / flask / pywebview）
# ============================================================
Write-Host "==> [DEPS] 检查并安装依赖..." -ForegroundColor Cyan
& python -m pip install --quiet --upgrade pip 2>&1 | Out-Null
& python -m pip install --quiet pyinstaller pystray pillow flask pywebview python-dotenv 2>&1 | Out-Null
# 校验 pywebview 真的可用（pywebview 老版本无 __version__，所以做 try/except 打印 ok/err）
$PV_OK = & python -c "try:`n import webview`n print('installed', end='')`nexcept Exception as e:`n print('ERR: '+str(e), end='')" 2>$null
if (-not $PV_OK -or $PV_OK -like "ERR:*") { Write-Host "[WARN] pywebview 不可用（$PV_OK），打包后若本机缺 Edge WebView2 会退化为默认浏览器打开" -ForegroundColor Yellow }
else             { Write-Host "    pywebview: $PV_OK" -ForegroundColor Gray }

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null

# ============================================================
# 2) 清理旧产物 + 调用 PyInstaller
# ============================================================
Write-Host "==> [CLEAN] 清理旧输出..." -ForegroundColor Cyan
Remove-Item -Recurse -Force (Join-Path $WorkDir "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $DistRoot "CrossHub-Sync-Helper") -ErrorAction SilentlyContinue

if ($OneFile) {
    Write-Host "==> [BUILD] --onefile 模式（单 EXE，部署方便，启动稍慢；桌面窗口版，需 -AllowDesktop 显式授权）" -ForegroundColor Cyan
    $ArgList = @(
        "--noconfirm","--clean",
        "--onefile",
        "--windowed",
        "--name","CrossHub-Sync-Helper",
        "--distpath",$DistRoot,
        "--workpath",(Join-Path $WorkDir "build"),
        "--specpath",(Join-Path $WorkDir "spec"),
        "--paths",$PyRoot,
        "--icon",$Icon,
        "--version-file",$VersionRes,
        "--add-data","$PyRoot\agent\panel;agent/panel",
        "--hidden-import","webview","--hidden-import","webview.platforms","--hidden-import","webview.platforms.edgechromium",
        "--hidden-import","agent","--hidden-import","agent.tray_app","--hidden-import","agent.health_server",
        "--hidden-import","flask","--hidden-import","pystray","--hidden-import","PIL","--hidden-import","PIL.Image",
        "--collect-submodules","agent","--collect-submodules","app","--collect-submodules","webview",
        $Entry
    )
} else {
    Write-Host "==> [BUILD] --onedir 模式（多文件，启动快，后续可独立热更 panel）" -ForegroundColor Cyan
    $ArgList = @(
        "--noconfirm","--clean",
        "--distpath",$DistRoot,
        "--workpath",(Join-Path $WorkDir "build"),
        $SpecPath
    )
}

Write-Host "    python -m PyInstaller $($ArgList -join ' ')" -ForegroundColor DarkGray
& python -m PyInstaller @ArgList
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FATAL] PyInstaller failed with exit $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# ============================================================
# 3) 定位输出 + 拷贝辅助文件 + 生成 config.json
# ============================================================
if ($OneFile) {
    $AppDir = $DistRoot
    $ExePath = Join-Path $AppDir "CrossHub-Sync-Helper.exe"
} else {
    $AppDir = Join-Path $DistRoot "CrossHub-Sync-Helper"
    $ExePath = Join-Path $AppDir "CrossHub-Sync-Helper.exe"
    if (-not (Test-Path $ExePath)) {
        $AppDir = $DistRoot
        $ExePath = Join-Path $AppDir "CrossHub-Sync-Helper.exe"
    }
}
if (-not (Test-Path $ExePath)) {
    Write-Host "[FATAL] 没找到输出的 EXE: $ExePath" -ForegroundColor Red
    exit 5
}

Write-Host "==> [ASSETS] 拷贝辅助文件到: $AppDir" -ForegroundColor Cyan
$example = Join-Path $Assets "config.example.json"
$cfgOut  = Join-Path $AppDir "config.example.json"
Copy-Item -Force $example $cfgOut -ErrorAction SilentlyContinue
$cfgLive = Join-Path $AppDir "config.json"
if (-not (Test-Path $cfgLive) -and (Test-Path $example)) {
    try {
        $obj = Get-Content $example -Raw -Encoding UTF8 | ConvertFrom-Json
        $obj.java_api_url = $JavaApiUrl
        if ($obj.PSObject.Properties.Name -contains "project_root")        { $obj.project_root = "%APPDATA%\CrossHubSyncHelper" }
        if ($obj.PSObject.Properties.Name -contains "temu_profile_root")  { $obj.temu_profile_root  = "%APPDATA%\CrossHubSyncHelper\.temu-browser-profile" }
        if ($obj.PSObject.Properties.Name -contains "ae_profile_root")    { $obj.ae_profile_root    = "%APPDATA%\CrossHubSyncHelper\.aliexpress-browser-profile" }
        if ($obj.PSObject.Properties.Name -contains "a1688_profile_root") { $obj.a1688_profile_root = "%APPDATA%\CrossHubSyncHelper\.1688-browser-profile" }
        if ($obj.PSObject.Properties.Name -contains "pdd_profile_root")    { $obj.pdd_profile_root    = "%APPDATA%\CrossHubSyncHelper" }
        ($obj | ConvertTo-Json -Depth 5) | Set-Content -Path $cfgLive -Encoding UTF8
    } catch {
        Write-Host " [WARN] 写 config.json 失败，已保留 config.example.json 供手动复制" -ForegroundColor Yellow
    }
}
Copy-Item -Force (Join-Path $Assets "register-protocol.ps1") (Join-Path $AppDir "register-protocol.ps1") -ErrorAction SilentlyContinue
Copy-Item -Force (Join-Path $Assets "SETUP.cmd")              (Join-Path $AppDir "SETUP.cmd")              -ErrorAction SilentlyContinue
Copy-Item -Force $Icon                                                    (Join-Path $AppDir "CrossHub.ico")           -ErrorAction SilentlyContinue

# ============================================================
# 4) 最终校验：PE 头 x64 + 版本资源 + 文件大小
# ============================================================
Write-Host ""
Write-Host "==> [VERIFY] 最终 EXE 完整性校验（PE 头 + 版本资源）" -ForegroundColor Cyan
$VerifyPy = @'
import sys, os, struct
p = r"__EXE__"
if not os.path.exists(p):
    print("EXE_MISSING"); sys.exit(1)
size = os.path.getsize(p)
with open(p,"rb") as f:
    head = f.read(0x1000)
if head[0:2] != b"MZ":
    print("NOT_PE"); sys.exit(2)
e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
pe_sig = head[e_lfanew:e_lfanew+4]
if pe_sig != b"PE\x00\x00":
    print("BAD_PE_SIG"); sys.exit(3)
machine = struct.unpack_from("<H", head, e_lfanew + 4)[0]
chars   = struct.unpack_from("<H", head, e_lfanew + 4 + 16)[0]  # COFF Characteristics
subsystem_off = e_lfanew + 4 + 20 + 68   # PE32/PE32+ OptionalHeader Subsystem (same offset for both)
subsystem = struct.unpack_from("<H", head, subsystem_off)[0]  # 2=GUI, 3=CUI
mapping = {0x8664:"x64_AMD64", 0x014c:"x86_I386", 0xAA64:"ARM64"}
arch = mapping.get(machine, hex(machine))
is_gui = subsystem == 2

ver, desc, company, product = "", "", "", ""
try:
    from win32api import GetFileVersionInfo, LOWORD, HIWORD
    vi = GetFileVersionInfo(p, "\\")
    ms = vi['FileVersionMS']; ls = vi['FileVersionLS']
    ver = f"{HIWORD(ms)}.{LOWORD(ms)}.{HIWORD(ls)}.{LOWORD(ls)}"
    for lang, cp in [(2052,1200),(1033,1200)]:
        try:
            desc    = desc    or GetFileVersionInfo(p, rf"\StringFileInfo\{lang:04x}{cp:04x}\FileDescription") or ""
            company = company or GetFileVersionInfo(p, rf"\StringFileInfo\{lang:04x}{cp:04x}\CompanyName")     or ""
            product = product or GetFileVersionInfo(p, rf"\StringFileInfo\{lang:04x}{cp:04x}\ProductName")     or ""
        except Exception:
            pass
except Exception:
    pass
# Heuristic for icon group resource: read bytes near .rsrc, just report size threshold
has_icon_bytes = size > 15_000_000   # bundled GUI exe should easily exceed this

print(f"SIZE={size}")
print(f"ARCH={arch}")
print(f"MACHINE=0x{machine:04X}")
print(f"SUBSYSTEM={'GUI' if is_gui else 'CUI(console)'}")
print(f"FILEVER={ver}")
print(f"DESC={desc}")
print(f"COMPANY={company}")
print(f"PRODUCT={product}")
print(f"HAS_ICON_HINT={has_icon_bytes}")
'@
# 把 Python 脚本写到临时文件，避免 PowerShell 字符串替换时引号/反斜杠被吞掉
$TmpPy = Join-Path $env:TEMP ("verify_pe_" + [guid]::NewGuid().ToString("N") + ".py")
# 手动替换 __EXE__：把路径按 Python 字符串字面量转义（先反斜杠再双引号）
$escapedPath = $ExePath.Replace('\', '\\').Replace('"', '\"')
$PyScript = $VerifyPy.Replace('"__EXE__"', '"' + $escapedPath + '"')
[System.IO.File]::WriteAllText($TmpPy, $PyScript, [System.Text.Encoding]::UTF8)
$PyOut  = (& python $TmpPy 2>&1)
Remove-Item $TmpPy -Force -ErrorAction SilentlyContinue
Write-Host ($PyOut -join "`n")

$ARCH    = ($PyOut | Select-String "^ARCH=(.+)"      ).Matches.Groups[1].Value
$MACH    = ($PyOut | Select-String "^MACHINE=(.+)"   ).Matches.Groups[1].Value
$SUBSYS  = ($PyOut | Select-String "^SUBSYSTEM=(.+)" ).Matches.Groups[1].Value
$FVER    = ($PyOut | Select-String "^FILEVER=(.+)"   ).Matches.Groups[1].Value
$DESC    = ($PyOut | Select-String "^DESC=(.+)"      ).Matches.Groups[1].Value

if ($ARCH -ne "x64_AMD64") {
    Write-Host "[FATAL] 最终 EXE 不是 x64 AMD64！当前 = $ARCH ($MACH)" -ForegroundColor Red
    exit 20
}
if ($SUBSYS -notlike "GUI*") {
    Write-Host "[WARN] EXE 子系统不是 GUI（可能会出现黑框控制台），SUBSYSTEM=$SUBSYS" -ForegroundColor Yellow
}

# ============================================================
# 5) README + 完成汇总
# ============================================================
$readme = @"
CrossHub Sync Helper · 桌面端（64 位 · 真窗口版）
=================================================
架构：            x64 (AMD64) — 仅限 64 位 Windows 10/11
可执行文件：      CrossHub-Sync-Helper.exe
子系统：          GUI（无控制台黑框）
文件版本：        $($FVER -replace '^=','')
文件描述：        $DESC
图标：            CrossHub.ico（16~256 多尺寸，任务栏/桌面/开始菜单自适应）
启动模式：        双击 EXE → 直接弹出桌面窗口（pywebview + Edge WebView2）
                  若本机未装 WebView2 会自动退化为默认浏览器打开

【首次使用 · 必做】
1. 将整个 CrossHub-Sync-Helper 文件夹拷贝到任意目录（如桌面或 %PROGRAMFILES%）。
2. 双击 CrossHub-Sync-Helper.exe（或 SETUP.cmd：会顺便注册 crosshub-sync-helper:// 协议）。
3. 程序启动后自动弹出桌面窗口，完成绑定码 / 账号密码绑定。
4. 保持程序运行（可最小化；托盘图标右键可「打开面板 / 退出」）。
5. 网站状态栏显示「助手在线」后，即可使用打开登录 / 同步订单 / 同步商品等功能。

【日常使用】
- 直接双击 EXE；如已运行会复用单实例，避免重复启动。
- 网站「连接助手」按钮可通过 crosshub-sync-helper:// 协议自动唤起。
- Playwright Chromium 若缺失：python -m playwright install chromium

文件清单：
  CrossHub-Sync-Helper.exe    主程序（x64 / GUI / 无控制台 / 带图标版本资源）
  SETUP.cmd                   一键注册协议 + 启动
  register-protocol.ps1       协议注册脚本
  config.json                 运行配置（一般不改）
  CrossHub.ico                应用图标
  README.txt                  本文件

"@
Set-Content -Path (Join-Path $AppDir "README.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host " 打包完成！ CrossHub Sync Helper 桌面版"        -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host " 目录     : $AppDir"                             -ForegroundColor Green
Write-Host " EXE      : $ExePath"                            -ForegroundColor Green
Write-Host " 架构     : $ARCH  ($MACH)"                      -ForegroundColor Green
Write-Host " 子系统   : $SUBSYS  (GUI=无黑框)"                -ForegroundColor Green
Write-Host " 版本     : $FVER"                                -ForegroundColor Green
Write-Host " 描述     : $DESC"                                -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
if (-not $OneFile) {
    Write-Host " 提示: 如需单 EXE，请加 -OneFile 参数；如需修改 JavaApiUrl 请用 -JavaApiUrl。"
}
exit 0
