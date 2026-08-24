[Setup]
AppId={{D1A780CB-B9C6-4F0B-9FF6-EEA4D2EC8D66}
AppName=Speak to Bridge
#ifndef AppVersion
  #error AppVersion must be supplied by build.ps1 from SpeakToBridge.constants.APP_VERSION
#endif
AppVersion={#AppVersion}
AppPublisher=Shrey Bhatt
AppCopyright=Copyright (C) 2026 Shrey Bhatt
DefaultDirName={autopf}\SpeakToBridge
DefaultGroupName=Speak to Bridge
UsePreviousGroup=no
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=SpeakToBridge-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\SpeakToBridge.exe
CloseApplications=force
CloseApplicationsFilter=SpeakToBridge.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\SpeakToBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"
Name: "{autodesktop}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SpeakToBridge.exe"; Description: "Launch Speak to Bridge"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\SpeakToBridge.exe"; Parameters: "--shutdown-for-uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "ShutdownSpeakToBridge"
