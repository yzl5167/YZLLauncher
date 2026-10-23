; YZL Launcher - Inno Setup installer script (ASCII/English to avoid encoding issues)
#define MyAppName "YZL Launcher"
#define MyAppVersion "1.4.7"
#define MyAppPublisher "YZL"
#define MyAppExeName "YZLLauncher.exe"

[Setup]
AppId={{8F2B4A6E-7C3D-4A5F-9B1E-5A0C4E1F0D2B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\YZL
PrivilegesRequired=lowest
DefaultGroupName=YZL
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=YZLLauncher-Setup-{#MyAppVersion}
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent