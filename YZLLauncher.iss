; YZL 启动器 - Inno Setup 独立安装包脚本

#define MyAppName "YZL 启动器"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "YZL"
#define MyAppExeName "YZLLauncher.exe"

[Setup]
AppId={{8F2B4A6E-7C3D-4A5F-9B1E-5A0C4E1F0D2B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\YZL启动器
DefaultGroupName=YZL 启动器
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=YZLLauncher-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent
