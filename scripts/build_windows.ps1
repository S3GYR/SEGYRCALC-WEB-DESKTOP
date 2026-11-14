#requires -Version 7.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Evidence = Join-Path (Split-Path -Parent $Root) "evidence\web-windows-packaging-07"
$LogDir = Join-Path $Evidence "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
$Iscc = "C:\Program Files\Inno Setup 7\ISCC.exe"

if (-not (Test-Path $Python)) { throw "Venv Python introuvable: $Python" }
if (-not (Test-Path $PyInstaller)) { throw "PyInstaller introuvable: $PyInstaller" }
if (-not (Test-Path $Iscc)) { throw "Inno Setup ISCC introuvable: $Iscc" }

Write-Host "[1/7] Vérification environnement"
& $Python -c "import sys, sqlite3, _sqlite3; print(sys.executable); print(sys.version); print(sqlite3.sqlite_version)" *> (Join-Path $LogDir "build-environment.txt")
& $Python -m pip check *>> (Join-Path $LogDir "build-environment.txt")
Push-Location (Join-Path $Root "frontend")
try {
    Write-Host "[2/7] Installation et build frontend"
    npm ci *> (Join-Path $LogDir "frontend-build.txt")
    npm run build *>> (Join-Path $LogDir "frontend-build.txt")
} finally { Pop-Location }

Push-Location $Root
try {
    Write-Host "[3/7] Build exécutable console de qualification"
    & $PyInstaller --noconfirm --clean --distpath (Join-Path $Root "dist-debug") --workpath (Join-Path $Root "build-debug") (Join-Path $Root "packaging\SEGYRCALC-debug.spec") *> (Join-Path $LogDir "pyinstaller-debug.txt")
    Write-Host "[4/7] Build exécutable Windows final"
    & $PyInstaller --noconfirm --clean --distpath (Join-Path $Root "dist") --workpath (Join-Path $Root "build") (Join-Path $Root "packaging\SEGYRCALC.spec") *> (Join-Path $LogDir "pyinstaller-final.txt")
    Write-Host "[5/7] Build installateur Inno Setup"
    & $Iscc (Join-Path $Root "installer\SEGYRCALC.iss") *> (Join-Path $LogDir "installer-build.txt")
} finally { Pop-Location }

Write-Host "[6/7] Vérification des artefacts"
$Artifacts = @(
    (Join-Path $Root "dist\SEGYRCALC\SEGYRCALC.exe"),
    (Join-Path $Root "dist-installer\SEGYRCALC-Setup-0.7.0-qualification.exe")
)
foreach ($Artifact in $Artifacts) {
    if (-not (Test-Path $Artifact)) { throw "Artefact manquant: $Artifact" }
}
$HashLines = foreach ($Artifact in $Artifacts) {
    $Hash = (Get-FileHash -Algorithm SHA256 $Artifact).Hash.ToUpper()
    "$Hash  $Artifact"
}
Set-Content -Path (Join-Path $Evidence "ARTIFACTS_SHA256.txt") -Value $HashLines -Encoding utf8

Write-Host "[7/7] Empreintes"
$SourceLines = Get-ChildItem $Root -Recurse -File | Where-Object {
    $_.FullName -notmatch '\\.venv\\|\\node_modules\\|\\dist\\|\\build\\|\\dist-debug\\|\\build-debug\\|\\dist-installer\\|\\qualification\\|\\__pycache__\\|\\.pytest_cache\\|\\.mypy_cache\\|\\.ruff_cache\\'
} | Sort-Object FullName | ForEach-Object {
    $Hash = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToUpper()
    $Relative = $_.FullName.Substring($Root.Length).TrimStart('\')
    "$Hash  $Relative"
}
Set-Content -Path (Join-Path $Evidence "SOURCE_SHA256.txt") -Value $SourceLines -Encoding utf8
Write-Host "Build terminé."
