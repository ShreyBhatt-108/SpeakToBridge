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
CloseApplicationsFilter=SpeakToBridge.exe,SeverusAI.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\SpeakToBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{app}\SeverusAI.exe"
Type: filesandordirs; Name: "{app}\_internal\SeverusAI"
Type: filesandordirs; Name: "{autoprograms}\Severus AI"
Type: files; Name: "{autodesktop}\Severus AI.lnk"

[Icons]
Name: "{group}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"
Name: "{autodesktop}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SpeakToBridge.exe"; Description: "Launch Speak to Bridge"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure ForceCleanupPath(const Target: string);
var
  Attempts: Integer;
begin
  if not DirExists(Target) then
    exit;

  for Attempts := 1 to 8 do
  begin
    if DelTree(Target, True, True, True) then
      exit;
    Sleep(500);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ForceCleanupPath(ExpandConstant('{app}'));
  end;
end;
