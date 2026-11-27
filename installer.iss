[Setup]
AppId={{8F3C2A71-5B9E-4D26-A1C4-7E0B9D3F6A52}
AppName=nocturne
AppVersion=1.1.0-beta
AppVerName=nocturne
AppPublisher=Adan
AppPublisherURL=https://github.com/muhdrasydan99/nocturne/
; Pasang per-user supaya program boleh tulis folder profiles
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Nocturne
DefaultGroupName=Nocturne
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=nocturne_setup_v1.1.0beta
SetupIconFile=nocturne.ico
UninstallDisplayIcon={app}\Nocturne.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

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
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/f /im Nocturne.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
  Result := True;
end;
