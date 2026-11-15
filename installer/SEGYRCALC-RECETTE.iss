#define MyAppName "SEGYRCALC - Recette Windows 11"
#define MyAppVersion "0.8.0-r6.2"
#define MyAppPublisher "SEGYR Technologies"
#define MyAppExeName "SEGYRCALC.exe"
#define MyAppId "{{9A7E6D21-4C8B-4F33-9A6D-2E7F5B1C8041}"

#ifndef MySourceDir
#define MySourceDir "..\dist\SEGYRCALC"
#endif
#ifndef MyOutputDir
#define MyOutputDir "..\dist-installer"
#endif
#ifndef MyOutputBaseFilename
#define MyOutputBaseFilename "SEGYRCALC-0.8.0-r6.2-WIN11-RECETTE-TRACEABLE-SETUP"
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
DefaultDirName={localappdata}\Programs\SEGYRCALC-RECETTE
DefaultGroupName=SEGYRCALC RECETTE WINDOWS 11
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
VersionInfoVersion=0.8.0.2
VersionInfoCompany=SEGYR Technologies
VersionInfoDescription=SEGYRCALC recette build {#MyBuildId}
VersionInfoProductName=SEGYRCALC - Recette Windows 11
VersionInfoProductVersion=0.8.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\SEGYRCALC - Recette Windows 11"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller SEGYRCALC - Recette Windows 11"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SEGYRCALC - Recette Windows 11"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer SEGYRCALC - Recette Windows 11"; Flags: nowait postinstall skipifsilent

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
