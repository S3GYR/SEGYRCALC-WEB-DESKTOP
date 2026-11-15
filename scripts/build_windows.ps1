#requires -Version 5.1
param(
    [string]$BuildRoot = $env:SEGYR_BUILD_ROOT,
    [string]$Python = $env:SEGYR_PYTHON_EXE,
    [string]$Iscc = $env:SEGYR_ISCC,
    [string]$InstallerName = "SEGYRCALC-0.8.0-r6.2-WIN11-RECETTE-TRACEABLE-SETUP.exe",
    [string]$EngineSource = $env:SEGYR_ENGINE_SOURCE,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RootFull = [IO.Path]::GetFullPath($Root)

if ([string]::IsNullOrWhiteSpace($BuildRoot)) {
    throw "SEGYR_BUILD_ROOT ou -BuildRoot est obligatoire. Le build doit rester hors du depot."
}
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
if ($BuildRoot.StartsWith($RootFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Le BuildRoot doit etre externe au depot: $BuildRoot"
}
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
$LogDir = Join-Path $BuildRoot "logs"
$FrontendDist = Join-Path $BuildRoot "frontend\dist"
$PyInstallerDist = Join-Path $BuildRoot "pyinstaller\dist"
$PyInstallerWork = Join-Path $BuildRoot "pyinstaller\work"
$InstallerDir = Join-Path $BuildRoot "installer"
$MetadataPath = Join-Path $BuildRoot "metadata\build-metadata.json"
$ManifestPath = Join-Path $BuildRoot "metadata\build-manifest.json"
foreach ($path in @($LogDir, $FrontendDist, $PyInstallerDist, $PyInstallerWork, $InstallerDir, (Split-Path $MetadataPath -Parent))) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path (Split-Path -Parent $Root) "python-env-r6.1\Scripts\python.exe")
    )
    $Python = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path $Python)) {
    throw "Python/PyInstaller introuvable. Definir SEGYR_PYTHON_EXE."
}
if ([string]::IsNullOrWhiteSpace($Iscc)) {
    $Iscc = "C:\Program Files\Inno Setup 7\ISCC.exe"
}
if (-not (Test-Path $Iscc)) {
    throw "Inno Setup ISCC introuvable: $Iscc"
}
if (-not [string]::IsNullOrWhiteSpace($EngineSource)) {
    if (-not (Test-Path $EngineSource)) { throw "Source moteur introuvable: $EngineSource" }
    $env:SEGYR_ENGINE_ROOT = Split-Path (Split-Path (Split-Path $EngineSource -Parent) -Parent) -Parent
}
$NodeModules = Join-Path $Root "frontend\node_modules"
$Tsc = Join-Path $NodeModules ".bin\tsc.cmd"
$Vitest = Join-Path $NodeModules ".bin\vitest.cmd"
$Vite = Join-Path $NodeModules ".bin\vite.cmd"
foreach ($tool in @($Tsc, $Vitest, $Vite)) {
    if (-not (Test-Path $tool)) {
        throw "Dependance frontend absente: $tool. Aucun npm ci automatique."
    }
}

function Invoke-Checked {
    param([scriptblock]$Action, [string]$Label)
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label a echoue avec le code $LASTEXITCODE"
    }
}

Write-Host "[1/7] Generer les metadonnees reelles"
$MetadataArgs = @(
    (Join-Path $Root "scripts\generate_build_metadata.py"),
    "--root", $Root,
    "--output", $MetadataPath,
    "--distribution", "Recette Windows 11"
)
if (-not [string]::IsNullOrWhiteSpace($EngineSource)) {
    $MetadataArgs += @("--engine-source", $EngineSource)
}
Invoke-Checked {
    & $Python @MetadataArgs
} "Generation des metadonnees"
$Meta = Get-Content $MetadataPath -Raw | ConvertFrom-Json
$env:SEGYR_FRONTEND_DIST = $FrontendDist
$env:SEGYR_BUILD_METADATA = $MetadataPath

Write-Host "[2/7] Typecheck et tests frontend"
Push-Location (Join-Path $Root "frontend")
try {
    if (-not $SkipTests) {
        Invoke-Checked { & $Tsc -b --pretty false } "Typecheck frontend"
        Invoke-Checked { & $Vitest run } "Tests frontend"
    }
    $env:VITE_BUILD_ID = [string]$Meta.build_id
    $env:VITE_BUILD_GIT_COMMIT = [string]$Meta.build_git_commit
    $env:VITE_BUILD_AT = [string]$Meta.build_at
    $env:VITE_BUILD_DISTRIBUTION = [string]$Meta.build_distribution
    Write-Host "[3/7] Build frontend isole"
    Invoke-Checked {
        & $Vite build --outDir $FrontendDist --emptyOutDir
    } "Build frontend"
} finally {
    Pop-Location
}
$FrontendAsset = Get-ChildItem (Join-Path $FrontendDist "assets") -Filter "*.js" | Select-Object -First 1
if (-not $FrontendAsset) { throw "Asset frontend absent dans $FrontendDist" }
$Injected = Select-String -Path $FrontendAsset.FullName -Pattern $Meta.build_id -SimpleMatch -Quiet
if (-not $Injected) { throw "BUILD_ID non injecte dans l'asset frontend" }

Write-Host "[4/7] Build PyInstaller isole"
Invoke-Checked {
    & $Python -m PyInstaller --noconfirm --clean `
        --distpath $PyInstallerDist --workpath $PyInstallerWork `
        (Join-Path $Root "packaging\SEGYRCALC.spec")
} "PyInstaller"
$PackagedExe = Join-Path $PyInstallerDist "SEGYRCALC\SEGYRCALC.exe"
$PackagedMetadata = Join-Path $PyInstallerDist "SEGYRCALC\_internal\build_metadata\build-metadata.json"
if (-not (Test-Path $PackagedExe)) { throw "Executable PyInstaller absent: $PackagedExe" }
if (-not (Test-Path $PackagedMetadata)) { throw "Manifeste de build absent du paquet: $PackagedMetadata" }

Write-Host "[5/7] Build installateur Inno Setup"
$InstallerPath = Join-Path $InstallerDir $InstallerName
Invoke-Checked {
    & $Iscc /Qp `
        "/DMySourceDir=$(Join-Path $PyInstallerDist 'SEGYRCALC')" `
        "/DMyOutputDir=$InstallerDir" `
        "/DMyOutputBaseFilename=$([IO.Path]::GetFileNameWithoutExtension($InstallerName))" `
        "/DMyBuildId=$($Meta.build_id)" `
        "/DMyIconFile=$(Join-Path $Root 'frontend\public\assets\segyrcalc.ico')" `
        (Join-Path $Root "installer\SEGYRCALC-RECETTE.iss")
} "Inno Setup"
if (-not (Test-Path $InstallerPath)) { throw "Installateur absent: $InstallerPath" }

Write-Host "[6/7] Ecrire le manifeste de build"
$InstallerHash = (Get-FileHash $InstallerPath -Algorithm SHA256).Hash.ToUpper()
$ExeHash = (Get-FileHash $PackagedExe -Algorithm SHA256).Hash.ToUpper()
$BuildManifest = [ordered]@{
    schema = "segyrcalc-build-manifest/v1"
    build = $Meta
    tools = [ordered]@{
        node = (& node --version 2>&1 | Out-String).Trim()
        npm = (& npm --version 2>&1 | Out-String).Trim()
        python = (& $Python --version 2>&1 | Out-String).Trim()
        pyinstaller = (& $Python -m PyInstaller --version 2>&1 | Out-String).Trim()
        inno_setup = (Get-Item $Iscc).VersionInfo.ProductVersion
        vite = (& $Vite --version 2>&1 | Out-String).Trim()
    }
    artifacts = [ordered]@{
        frontend_dist = $FrontendDist
        executable = $PackagedExe
        executable_sha256 = $ExeHash
        installer = $InstallerPath
        installer_sha256 = $InstallerHash
        installer_size = (Get-Item $InstallerPath).Length
    }
}
$BuildManifest | ConvertTo-Json -Depth 8 | Set-Content -Path $ManifestPath -Encoding utf8
Set-Content -Path (Join-Path $InstallerDir "INSTALLER_SHA256.txt") -Value "$InstallerHash  $InstallerName" -Encoding utf8

Write-Host "[7/7] Verification finale"
$PackagedMeta = Get-Content $PackagedMetadata -Raw | ConvertFrom-Json
if ($PackagedMeta.build_id -ne $Meta.build_id) { throw "BUILD_ID incoherent dans le paquet" }
if ($PackagedMeta.build_git_commit -ne $Meta.build_git_commit) { throw "Commit incoherent dans le paquet" }
Write-Host "BUILD_ID=$($Meta.build_id)"
Write-Host "BUILD_GIT_COMMIT=$($Meta.build_git_commit)"
Write-Host "BUILD_AT=$($Meta.build_at)"
Write-Host "BUILD_DISTRIBUTION=$($Meta.build_distribution)"
Write-Host "BUILD_SOURCE_STATE=$($Meta.build_source_state)"
Write-Host "INSTALLER=$InstallerPath"
Write-Host "INSTALLER_SHA256=$InstallerHash"
