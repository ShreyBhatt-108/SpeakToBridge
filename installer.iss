[Setup]
AppId={{D1A780CB-B9C6-4F0B-9FF6-EEA4D2EC8D66}
AppName=Severus AI
AppVersion=1.1.2
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
CloseApplications=force
CloseApplicationsFilter=SeverusAI.exe
RestartApplications=no
SetupLogging=yes

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

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\SeverusAI"

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
    ForceCleanupPath(ExpandConstant('{localappdata}\SeverusAI'));
  end;
end;
