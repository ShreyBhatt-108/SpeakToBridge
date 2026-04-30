[Setup]
AppId={{D1A780CB-B9C6-4F0B-9FF6-EEA4D2EC8D66}
AppName=Severus AI
AppVersion=0.1.0
AppPublisher=Shrey Bhatt
AppCopyright=Copyright (C) 2026 Shrey Bhatt
DefaultDirName={autopf}\SeverusAI
DefaultGroupName=Severus AI
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=SeverusAI-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\SeverusAI.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\SeverusAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Severus AI"; Filename: "{app}\SeverusAI.exe"
Name: "{autodesktop}\Severus AI"; Filename: "{app}\SeverusAI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SeverusAI.exe"; Description: "Launch Severus AI"; Flags: nowait postinstall skipifsilent
