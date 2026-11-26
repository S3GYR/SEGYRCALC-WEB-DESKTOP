#define MyAppName "SEGYRCALC BETA"
#define MyAppVersion "0.9.0-beta.1"
#define MyAppPublisher "SEGYR Technologies"
#define MyAppExeName "SEGYRCALC.exe"
#define MyAppId "{{B6D2F7A4-3C8E-4A1B-9F52-7E1D4C8A2B63}"

#ifndef MySourceDir
#define MySourceDir "..\dist\SEGYRCALC"
#endif
#ifndef MyOutputDir
#define MyOutputDir "..\dist-installer-beta"
#endif
#ifndef MyOutputBaseFilename
#define MyOutputBaseFilename "SEGYRCALC-0.9.0-beta.1-WIN11-x64-SETUP"
#endif
#ifndef MyBuildId
#define MyBuildId "UNSPECIFIED"
#endif
#ifndef MyIconFile
#define MyIconFile "..\frontend\public\assets\segyrcalc.ico"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SEGYRCALC-BETA
DefaultGroupName=SEGYRCALC BETA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile={#MyIconFile}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=SEGYRCALC-BETA-NOTICE.txt
VersionInfoVersion=0.9.0.1
VersionInfoCompany=SEGYR Technologies
VersionInfoDescription=SEGYRCALC BETA build {#MyBuildId}
VersionInfoProductName=SEGYRCALC BETA
VersionInfoProductVersion=0.9.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SEGYRCALC BETA"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller SEGYRCALC BETA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SEGYRCALC BETA"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer SEGYRCALC BETA"; Flags: nowait postinstall skipifsilent

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
    MsgBox('Microsoft Edge WebView2 Runtime est requis. Installez le runtime officiel Microsoft avant SEGYRCALC BETA. Aucun téléchargement automatique n''est effectué.', mbError, MB_OK);
    Result := False;
  end;
end;
