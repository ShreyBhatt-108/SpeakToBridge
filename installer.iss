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
#ifndef OutputName
  #define OutputName "SpeakToBridge-Setup"
#endif
OutputBaseFilename={#OutputName}
Compression=lzma2
LZMANumBlockThreads=2
LZMAUseSeparateProcess=yes
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\SpeakToBridge.exe
CloseApplications=yes
CloseApplicationsFilter=SpeakToBridge.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

#ifndef AppSourceDir
  #define AppSourceDir "dist\SpeakToBridge"
#endif

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Replace packaged dependencies when switching CPU/AMD builds or Python ABIs.
; User settings and models live separately in LOCALAPPDATA\SpeakToBridge.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"
Name: "{autodesktop}\Speak to Bridge"; Filename: "{app}\SpeakToBridge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SpeakToBridge.exe"; Description: "Launch Speak to Bridge"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\SpeakToBridge.exe"; Parameters: "--shutdown-for-uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "ShutdownSpeakToBridge"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  AppExecutable: String;
  ResultCode: Integer;
begin
  Result := '';
  AppExecutable := ExpandConstant('{app}\SpeakToBridge.exe');
  if FileExists(AppExecutable) then
  begin
    { Ask the existing app to save pending Word Bank edits and release workers. }
    { Never elevate an existing executable in a per-user installation folder. }
    if not ExecAsOriginalUser(AppExecutable, '--shutdown-for-uninstall', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode) then
      Result := 'Please close Speak to Bridge before continuing the installation.'
    else if ResultCode <> 0 then
      Result := 'Speak to Bridge could not close safely. Close it and retry installation.';
  end;
end;
