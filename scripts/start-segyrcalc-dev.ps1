#requires -Version 5.1
param(
    [int]$Port = 8000,
    [string]$Python = "",
    [string]$EngineSrc = "",
    [switch]$Rebuild,
    [switch]$NoBrowser,
    [switch]$NoSeed,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "logs"
$DistDir = Join-Path $Root "frontend\dist"
$PidFile = Join-Path $LogDir "dev-server.pid"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Stop-ServerTree([int]$ServerPid) {
    $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $ServerPid" -ErrorAction SilentlyContinue).CommandLine
    if ($commandLine -notmatch "uvicorn\s+backend\.main:app") {
        throw "Le PID $ServerPid n'est pas un serveur SEGYRCALC reconnu. Arrêt refusé."
    }
    taskkill.exe /PID $ServerPid /T /F *> $null
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 128) {
        throw "Échec de l'arrêt de l'arbre de processus $ServerPid."
    }
}

function Stop-DevServer {
    if (-not (Test-Path $PidFile)) {
        throw "Aucun serveur de développement enregistré."
    }
    $serverPid = [int](Get-Content $PidFile -Raw).Trim()
    $process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "Aucun processus vivant pour le PID enregistré."
        return
    }
    Stop-ServerTree -ServerPid $serverPid
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Serveur SEGYRCALC de développement arrêté (PID $serverPid)."
}

if ($Stop) {
    Stop-DevServer
    return
}

if (-not $Python) {
    $Python = Join-Path $Root "..\..\python-env-r6.1\Scripts\python.exe"
}
$Python = [IO.Path]::GetFullPath($Python)
if (-not (Test-Path $Python)) {
    throw "Python de qualification introuvable: $Python"
}
if (-not $EngineSrc) {
    $EngineSrc = [IO.Path]::GetFullPath((Join-Path $Root "..\..\..\SEGYRCALC-V1.5-UI-ERGONOMIE-01\worktree\src"))
}
$EngineSrc = [IO.Path]::GetFullPath($EngineSrc)
$Fixture = Join-Path (Split-Path -Parent $EngineSrc) "examples\recette-business-acceptance-v1.3.json"
if (-not (Test-Path (Join-Path $EngineSrc "segyr_calc\core\power.py"))) {
    throw "Moteur électrique introuvable: $EngineSrc"
}
if (-not (Test-Path (Join-Path $EngineSrc "calcelect\service_v13.py"))) {
    throw "Façade calcelect.service_v13 introuvable: $EngineSrc"
}
if (-not (Test-Path $Fixture)) {
    throw "Fixture de recette V1.3 introuvable: $Fixture"
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules\.bin\vite.cmd"))) {
    throw "Dépendances frontend absentes. Ce lanceur ne les installe pas."
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules\.bin\tsc.cmd"))) {
    throw "TypeScript frontend absent. Ce lanceur ne l'installe pas."
}
$npm = (Get-Command npm -ErrorAction SilentlyContinue)
if (-not $npm) {
    throw "npm introuvable dans le PATH du terminal."
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($previousPythonPath) { "$EngineSrc;$previousPythonPath" } else { $EngineSrc }
$dependencyProbe = & $Python -c "import fastapi, uvicorn, pydantic; from calcelect.service_v13 import calculate_project_v13; from segyr_calc.core.power import calculate_power; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or ($dependencyProbe -notcontains "OK")) {
    throw "Dépendances Python indisponibles. Vérifier fastapi, uvicorn, pydantic, calcelect et segyr_calc. Détail: $dependencyProbe"
}

$dataRoot = Join-Path $Root "qualification-dev-data"
$projectsRoot = Join-Path $dataRoot "Projects"
$exportsRoot = Join-Path $dataRoot "Exports"
$runtimeLogs = Join-Path $dataRoot "Logs"
foreach ($path in @($dataRoot, $projectsRoot, $exportsRoot, $runtimeLogs)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$env:SEGYR_ENGINE_SRC = $EngineSrc
$env:SEGYR_PROJECT_FIXTURE = $Fixture
$env:SEGYR_USER_DATA_ROOT = $dataRoot
$env:SEGYR_PROJECTS_ROOT = $projectsRoot
$env:SEGYR_EXPORTS_ROOT = $exportsRoot
$env:SEGYR_LOGS_ROOT = $runtimeLogs

$fixtureCopy = Join-Path $projectsRoot ([IO.Path]::GetFileName($Fixture))
if (-not $NoSeed -and -not (Test-Path $fixtureCopy)) {
    Copy-Item -LiteralPath $Fixture -Destination $fixtureCopy
    Write-Host "Jeu de recette V1.3 copié dans le stockage de développement isolé."
}

if ($Rebuild -or -not (Test-Path (Join-Path $DistDir "index.html"))) {
    Write-Host "Compilation du frontend..."
    Push-Location (Join-Path $Root "frontend")
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $npm.Source run build *> (Join-Path $LogDir "dev-frontend-build.log")
        $buildExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
        Pop-Location
    }
    if ($buildExit -ne 0) {
        throw "Échec de la compilation frontend. Voir logs\dev-frontend-build.log."
    }
}
if (-not (Test-Path (Join-Path $DistDir "index.html"))) {
    throw "Éléments frontend compilés introuvables: $DistDir"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Le port $Port est déjà utilisé. Aucun processus existant n'a été arrêté."
}

$stdout = Join-Path $LogDir "dev-server.out.log"
$stderr = Join-Path $LogDir "dev-server.err.log"
$process = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "uvicorn", "backend.main:app",
    "--host", "127.0.0.1", "--port", "$Port", "--log-level", "warning"
) -WorkingDirectory $Root -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii

$baseUrl = "http://127.0.0.1:$Port/"
$token = $null
try {
    for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
        Start-Sleep -Milliseconds 500
        try {
            $index = Invoke-WebRequest -Uri $baseUrl -UseBasicParsing -TimeoutSec 3
            $match = [regex]::Match($index.Content, 'name="segyr-session-token" content="([^"]+)"')
            if ($index.StatusCode -eq 200 -and $match.Success) {
                $token = $match.Groups[1].Value
                break
            }
        } catch {
            if ($process.HasExited) {
                throw "Le serveur backend s'est arrêté pendant le démarrage. Voir logs\dev-server.err.log."
            }
        }
    }
    if (-not $token) {
        throw "Le serveur n'a pas fourni d'interface avec jeton injecté. Voir logs\dev-server.err.log."
    }
    $health = Invoke-WebRequest -Uri ($baseUrl + "api/health") -Headers @{"X-SEGYR-Token" = $token} -UseBasicParsing -TimeoutSec 5
    if ($health.StatusCode -ne 200) {
        throw "Le contrôle de santé backend a échoué (HTTP $($health.StatusCode))."
    }
    $assetReferences = [regex]::Matches($index.Content, '(?:src|href)="(/assets/[^"]+)"') | ForEach-Object { $_.Groups[1].Value }
    $scriptAssets = @($assetReferences | Where-Object { $_ -match '\.js(?:\?|$)' })
    $styleAssets = @($assetReferences | Where-Object { $_ -match '\.css(?:\?|$)' })
    if ($scriptAssets.Count -eq 0 -or $styleAssets.Count -eq 0) {
        throw "Le HTML servi ne référence pas les ressources JavaScript et CSS attendues."
    }
    foreach ($asset in $assetReferences) {
        $assetResponse = Invoke-WebRequest -Uri ($baseUrl.TrimEnd("/") + $asset) -UseBasicParsing -TimeoutSec 10
        if ($assetResponse.StatusCode -ne 200) {
            throw "Ressource frontend indisponible (HTTP $($assetResponse.StatusCode)): $asset"
        }
        $contentType = [string]$assetResponse.Headers["Content-Type"]
        if ($asset -match '\.js(?:\?|$)' -and $contentType -notmatch "javascript") {
            throw "Type MIME JavaScript invalide pour $asset : $contentType"
        }
        if ($asset -match '\.css(?:\?|$)' -and $contentType -notmatch "text/css") {
            throw "Type MIME CSS invalide pour $asset : $contentType"
        }
    }
    if (-not $NoBrowser) {
        $launchUrl = $baseUrl + "?launch=" + (Get-Date -Format "yyyyMMddHHmmssfff")
        Start-Process $launchUrl
    }
    Write-Host "SEGYRCALC dev démarré."
    Write-Host "URL: $baseUrl"
    Write-Host "PID: $($process.Id)"
    Write-Host "Arrêt: .\scripts\start-segyrcalc-dev.ps1 -Stop"
    try {
        Wait-Process -Id $process.Id
    } finally {
        if (-not $process.HasExited) {
            Stop-ServerTree -ServerPid $process.Id
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
} catch {
    if (-not $process.HasExited) {
        Stop-ServerTree -ServerPid $process.Id
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    throw
}
