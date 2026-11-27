#define MyAppVersion "1.1.0-beta"

[Setup]
AppId={{8F3C2A71-5B9E-4D26-A1C4-7E0B9D3F6A52}
AppName=nocturne
AppVersion={#MyAppVersion}
AppVerName=nocturne
AppPublisher=Adan
AppPublisherURL=https://github.com/muhdrasydan99/nocturne/
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Nocturne
DefaultGroupName=Nocturne
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=nocturne_setup_v{#MyAppVersion}
SetupIconFile=nocturne.ico
UninstallDisplayIcon={app}\Nocturne.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create shortcut in Desktop"; Flags: unchecked

[Files]
Source: "dist\Nocturne\*"; DestDir: "{app}"; Excludes: "\profiles"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Nocturne"; Filename: "{app}\Nocturne.exe"
Name: "{autodesktop}\Nocturne"; Filename: "{app}\Nocturne.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Nocturne.exe"; Description: "Open Nocturne"; Flags: nowait postinstall skipifsilent

[Code]
function IsNocturneRunning(): Boolean;
var
  WbemLocator, WbemServices, WbemObjectSet: Variant;
begin
  Result := False;
  try
    WbemLocator := CreateOleObject('WbemScripting.SWbemLocator');
    WbemServices := WbemLocator.ConnectServer('.', 'root\CIMV2');
    WbemObjectSet := WbemServices.ExecQuery('SELECT Name FROM Win32_Process WHERE Name = "Nocturne.exe" OR Name = "Nocturne.exe.old"');
    Result := (WbemObjectSet.Count > 0);
  except
    Result := False;
  end;
end;

procedure KillNocturneProcess();
var
  ResultCode: Integer;
  TaskKillPath: String;
begin
  TaskKillPath := ExpandConstant('{sys}\taskkill.exe');
  Exec(TaskKillPath, '/F /IM Nocturne.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(TaskKillPath, '/F /IM Nocturne.exe.old', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  OldExePath: String;
begin
    Result := '';
  if CompareText(ExpandConstant('{srcexe}'), ExpandConstant('{app}\Nocturne.exe')) = 0 then
  begin
    Result := 'This installer is running as Nocturne.exe. Download the setup file from GitHub Releases and run it directly.';
    Exit;
  end;
  KillNocturneProcess();

  while IsNocturneRunning() do
  begin
    if MsgBox('Nocturne is running. Please end the task.', mbError, MB_RETRYCANCEL) = IDCANCEL then
    begin
      Result := 'Failed to install as nocturne still running.';
      Exit;
    end;
    KillNocturneProcess();
  end;

  OldExePath := ExpandConstant('{app}\Nocturne.exe.old');
  if FileExists(OldExePath) then
    DeleteFile(OldExePath);
end;

function InitializeUninstall(): Boolean;
begin
  KillNocturneProcess();
  if IsNocturneRunning() then
  begin
    MsgBox('Close nocturne first (uninstall).', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;
