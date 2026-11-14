#define MyAppName "SEGYRCALC"
#define MyAppVersion "0.7.1"
#define MyAppPublisher "SEGYR Technologies"
#define MyAppExeName "SEGYRCALC.exe"
#define MyAppId "{{C4D8A2F1-6B3E-49A7-8F2C-5D1E7B9A3C62}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SEGYRCALC-WEB07-DIAG
DefaultGroupName=SEGYRCALC WEB-07 DIAGNOSTIC
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer-diag
OutputBaseFilename=SEGYRCALC-Setup-{#MyAppVersion}-qualification
SetupIconFile=..\frontend\public\assets\segyrcalc.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=0.7.1.0
VersionInfoCompany=SEGYR Technologies
VersionInfoDescription=SEGYRCALC WEB-07 DIAGNOSTIC qualification candidate
VersionInfoProductName=SEGYRCALC
VersionInfoProductVersion=0.7.1

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "..\dist-diag\SEGYRCALC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SEGYRCALC WEB-07 DIAGNOSTIC"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller SEGYRCALC WEB-07 DIAGNOSTIC"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SEGYRCALC WEB-07 DIAGNOSTIC"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer SEGYRCALC WEB-07 DIAGNOSTIC"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Code]
function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not WebView2Installed then
  begin
    MsgBox('Microsoft Edge WebView2 Runtime est requis. Installez le runtime officiel Microsoft avant SEGYRCALC. Aucun téléchargement automatique n''est effectué.', mbError, MB_OK);
    Result := False;
  end;
end;
