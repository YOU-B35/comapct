# CrossHub Sync Helper — 隐藏启动脚本 (PowerShell)
# 用途: 后台运行 Helper 应用，不显示任何 Python 窗口
# 使用: 在 PowerShell 中运行此脚本

param(
    [switch]$Admin = $false
)

# 检查是否需要管理员权限
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    Write-Warning "正在以管理员权限重新启动..."
    Start-Process PowerShell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# 获取脚本目录
$scriptDir = Split-Path -Parent $PSCommandPath
$pythonScript = Join-Path $scriptDir "backend\python\agent\desktop_app.py"

# 检查文件是否存在
if (-Not (Test-Path $pythonScript)) {
    [System.Windows.Forms.MessageBox]::Show("找不到启动文件: $pythonScript", "CrossHub Helper — 启动失败", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}

# 查找 pythonw.exe 或 python.exe
$pythonW = $(where.exe pythonw 2>$null) | Select-Object -First 1
$python = $(where.exe python 2>$null) | Select-Object -First 1

if (-Not $pythonW -And -Not $python) {
    [System.Windows.Forms.MessageBox]::Show("Python 未在系统 PATH 中。`n`n请先安装 Python 3.10+ 或配置系统环境变量。", "CrossHub Helper — 启动失败", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}

# 优先使用 pythonw（不显示窗口）
$python = $pythonW ?? $python

Write-Host "🚀 启动 CrossHub Sync Helper..."
Write-Host "Python: $python"
Write-Host "脚本: $pythonScript"

try {
    # 使用 CreateNoWindow 参数隐藏窗口
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $python
    $processInfo.Arguments = "`"$pythonScript`""
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardOutput = $false
    $processInfo.RedirectStandardError = $false

    # 设置工作目录为项目根目录
    $processInfo.WorkingDirectory = $scriptDir

    # 启动进程
    $process = [System.Diagnostics.Process]::Start($processInfo)

    if ($process) {
        Write-Host "✓ CrossHub Helper 已启动 (PID: $($process.Id))"
        Write-Host "`n💡 提示:"
        Write-Host "  • 应用已在后台运行"
        Write-Host "  • 桌面窗口将在 1-2 秒后出现"
        Write-Host "  • 如未出现，请检查日志: $scriptDir\logs\sync_helper.log"
        Write-Host "`n按 Ctrl+C 关闭此窗口（不会停止应用）"
    }
    else {
        throw "无法启动 Python 进程"
    }
}
catch {
    [System.Windows.Forms.MessageBox]::Show("启动失败: $_", "CrossHub Helper — 错误", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}

# 保持窗口打开，显示启动日志
Start-Sleep -Seconds 3
