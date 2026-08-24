; ================================================================
;  CrossHub Sync Helper · Windows 安装程序（Inno Setup）
; ---------------------------------------------------------------
;   · 标准安装向导（中文 / 英文双语）
;   · 安装到 {autopf}\CrossHub Sync Helper（可改）
;   · 创建「开始菜单」快捷方式 + 桌面快捷方式 + 卸载快捷方式
;   · 可选「开机自启」（当前用户，不需要管理员）
;   · 注册 crosshub-sync-helper:// 自定义 URL 协议（HKCU）
;   · 注册「应用 execution alias」：Win+R 输入 crosshub-sync-helper 直接启动
;   · 在「设置 → 应用 → 安装的应用 / 控制面板 → 程序和功能」中显示卸载项
;       （Publisher / Version / InstallDate / Size / HelpLink / UninstallString 齐全）
;   · 安装前关闭正在运行的 Helper，避免文件占用
;   · 可选代码签名：在编译前用 signtool 对 EXE + Setup.exe 双重签名
;   · 支持管理员/当前用户两种安装模式（PrivilegesRequired=lowest）
;
;   编译：
;       ISCC.exe scripts\packaging\sync-helper\CrossHub-Sync-Helper.iss
;       或直接执行 .\scripts\build-and-package-installer.ps1 一键完成
; ================================================================

#define MyAppName      "CrossHub Sync Helper"
#define MyAppShortName "CrossHubSyncHelper"
#define MyAppVersion   "2.4.0.0"
#define MyAppPublisher "YOTO Tech"
#define MyAppURL       "https://www.yoto.work"
#define MyAppSupportURL "https://www.yoto.work/help"
#define MyAppUpdatesURL "https://www.yoto.work/downloads"
#define MyAppExeName   "CrossHub-Sync-Helper.exe"

[Setup]
; 基本信息 —— 对应「卸载」面板里显示的字段
AppId={{F7E4B3A1-2C5D-4F8A-9B71-62D0E3A1C812}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppSupportURL}
AppUpdatesURL={#MyAppUpdatesURL}

; 安装目录（优先按用户；有管理员权限时可切到 Program Files）
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 强校验：只允许在 x64 Windows 上安装（因为 EXE 是 x64）
; 格式：0（不限制 Win9x 系列）, <NT build>  17763 = Windows 10 1809
MinVersion=0,10.0.17763
SetupIconFile=CrossHub.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=License.rtf
; 如提供了侧边图，启用下两行：
; WizardSmallImageFile=WizSmallImage.bmp
; WizardImageFile=WizImage.bmp
WizardImageStretch=no

Compression=lzma2/ultra
LZMANumBlockThreads=4
InternalCompressLevel=ultra
OutputDir=..\..\..\dist\Installer
OutputBaseFilename=CrossHub-Sync-Helper-Setup-{#MyAppVersion}-x64

; 卸载面板字段（控制面板里能看到）
; ~114 MB 估计值（单位 KB）
UninstallDisplaySize=117188
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=CrossHub Sync Helper 安装程序 (x64)
VersionInfoProductName={#MyAppName} Desktop Setup

; 日志/禁用旧版覆盖安装前提示
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousGroup=yes
; 允许写 PATH 后立即生效通知（广播 WM_SETTINGCHANGE）
ChangesEnvironment=yes

[Languages]
; 默认用英文模板（Inno Setup 已内置）；界面描述全部使用中文，保持用户一致体验
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 任务清单：安装向导里用户可选勾
Name: "desktopicon";      Description: "{cm:CreateDesktopIcon}";      GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon";  Description: "创建任务栏快捷方式";           GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart";        Description: "开机自动启动（登录后自动运行）"; GroupDescription: "启动行为："; Flags: unchecked
Name: "runafter";         Description: "安装完成后立即运行 {#MyAppName}"; GroupDescription: "启动行为："; Flags: unchecked

[Files]
; 把 PyInstaller 打包后的整个 dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper\  内容复制到 {app}
Source: "..\..\..\dist\CrossHub-Sync-Helper\CrossHub-Sync-Helper\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs restartreplace; Excludes: "*.log;*.tmp;build\*;__pycache__\*"

; 许可证、快捷方式辅助脚本随包分发
Source: "License.rtf";   DestDir: {app}; Flags: ignoreversion
Source: "register-protocol.ps1"; DestDir: {app}; Flags: ignoreversion

[Icons]
; 开始菜单（程序组）
Name: "{group}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\CrossHub.ico"
Name: "{group}\打开绑定面板（浏览器）";      Filename: "http://127.0.0.1:18766/"; IconFilename: "{app}\CrossHub.ico"
Name: "{group}\配置文档（config.json）";    Filename: "{app}\config.json"; IconFilename: "shell32.dll,-17"
Name: "{group}\README 使用说明";            Filename: "{app}\README.txt"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "shell32.dll,-31"

; 桌面快捷方式（task: desktopicon）
Name: "{autodesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\CrossHub.ico"; Tasks: desktopicon

; 任务栏（Quick Launch = %APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar 需手动 pin；这里放 %APPDATA%\..\Roaming\Microsoft\Windows\Start Menu\Programs\Startup）
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\CrossHub.ico"; Tasks: quicklaunchicon

[Registry]
; (1) 自定义 URL 协议 crosshub-sync-helper:// —— HKCU（不需要管理员，Current User）
Root: HKCU; Subkey: "Software\Classes\crosshub-sync-helper";               ValueType: string; ValueName: "";           ValueData: "URL:CrossHub Sync Helper 协议"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\crosshub-sync-helper";               ValueType: string; ValueName: "URL Protocol"; ValueData: "";                 Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\crosshub-sync-helper\DefaultIcon";   ValueType: string; ValueName: "";           ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\crosshub-sync-helper\shell";         ValueType: string; ValueName: "";           ValueData: "open";                Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\crosshub-sync-helper\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

; (2) 开机自启（任务：autostart）—— HKCU\...\Run（当前用户级，无需管理员）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppShortName}"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

; (3) 应用别名（App Execution Aliases 风格：把 app Path 登记到 App Paths，Win+R 就能开）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\crosshub-sync-helper.exe"; ValueType: string; ValueName: "";         ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\crosshub-sync-helper.exe"; ValueType: string; ValueName: "Path";     ValueData: "{app}";                   Flags: uninsdeletevalue

; (4) 卸载面板的友好字段（Inno Setup 会自动建 Uninstall 键；这里再补几个常用 DisplayXxx 便于 IT 管理）
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
    ValueType: string; ValueName: "DisplayIcon";    ValueData: "{app}\{#MyAppExeName},0";         Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
    ValueType: string; ValueName: "Comments";       ValueData: "CrossHub Sync Helper 跨平台电商同步助手（本机运行端）"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
    ValueType: string; ValueName: "InstallLocation";ValueData: "{app}";                             Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1"; \
    ValueType: string; ValueName: "Contact";        ValueData: "support@yoto.work";                 Flags: uninsdeletevalue

[Run]
; 可选：安装完立刻运行
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent unchecked; Tasks: runafter

[UninstallRun]
; 卸载前安全退出正在运行的 Helper（避免文件被锁删不掉）
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall-cleanup"; RunOnceId: "CleanupOnUninstall"; Flags: waituntilterminated skipifdoesntexist runhidden

[Code]
// 安装前关闭 Helper 主程序（防止被锁）
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // 杀掉同名进程（温和 taskkill，不强制）
  if Exec('taskkill.exe', '/FI "IMAGENAME eq {#MyAppExeName}" /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Log('taskkill returned ' + IntToStr(ResultCode));
  end;
  // 稍等 800ms 让进程退出、释放文件句柄
  Sleep(800);
end;

// 安装完后强制刷新「设置」面板环境变量 / 协议 / 卸载项
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 广播 WM_SETTINGCHANGE：参数(HWND_BROADCAST, WM_SETTINGCHANGE, 0, LPARAM(PChar('Environment')))
    //   对应 code: 0xFFFF / 0x001A / 0 / (指针)Environment；Inno Pascal 用 SendMessage 形式
    Log('Installation complete. CrossHub Sync Helper installed to: ' + ExpandConstant('{app}'));
  end;
end;
