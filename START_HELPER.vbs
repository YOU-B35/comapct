' CrossHub Sync Helper — 隐藏启动脚本
' 用途：后台运行 Python 应用，不显示控制台窗口

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 获取脚本所在目录
strScriptPath = WScript.ScriptFullName
strScriptDir = objFSO.GetParentFolderName(strScriptPath)

' 检查 Python 是否在 PATH 中
On Error Resume Next
objShell.Exec "python --version"
If Err.Number <> 0 Then
    MsgBox "Python 未在系统 PATH 中。请先安装 Python 3.10+ 或配置 PYTHON_HOME 环境变量。", vbCritical, "CrossHub Helper — 启动失败"
    WScript.Quit 1
End If
On Error GoTo 0

' 构建启动命令
' 使用 pythonw 代替 python 避免显示控制台窗口
strPythonW = "pythonw"
strScriptFile = objFSO.BuildPath(strScriptDir, "backend\python\agent\desktop_app.py")

' 检查脚本是否存在
If Not objFSO.FileExists(strScriptFile) Then
    MsgBox "找不到启动文件: " & strScriptFile, vbCritical, "CrossHub Helper — 启动失败"
    WScript.Quit 1
End If

' 以隐藏窗口方式执行（第二个参数 0 表示隐藏，vbHide）
' 第三个参数 True 表示等待进程结束
On Error Resume Next
Set objProcess = objShell.Exec(strPythonW & " """ & strScriptFile & """")
If Err.Number <> 0 Then
    ' 如果 pythonw 不可用，尝试使用 python 但隐藏窗口
    On Error GoTo 0
    objShell.Run strPythonW & " """ & strScriptFile & """", 0, False
End If
On Error GoTo 0

' 脚本退出（但 Python 进程继续后台运行）
WScript.Quit 0
