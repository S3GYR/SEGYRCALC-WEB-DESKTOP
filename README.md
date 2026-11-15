# SEGYRCALC Web Desktop

Application locale Windows de calcul et de bilan de puissance électrique,
basée sur les moteurs historiques SEGYRCALC V1.4/V1.5 en lecture seule.

## Version de référence

```text
Baseline : R6.2
Version  : 0.8.0-r6.2
Date     : 2026-11-15
```

R6.2 est une version candidate de qualification isolée. Elle n'est ni une
version de production, ni une validation Windows 11 officielle.

## Architecture

```text
frontend/   React 18 + TypeScript + Vite
backend/    FastAPI loopback + pywebview/WebView2
packaging/  PyInstaller et lanceur Windows
scripts/    Outils de test, parité, preservation et construction
```

Le moteur de calcul n'est pas copié ni modifié par ce dépôt. Il est attendu
dans le worktree historique :

```text
..\..\SEGYRCALC-V1.5-UI-ERGONOMIE-01\worktree\src
```

Le chemin par défaut est résolu depuis l'emplacement du dépôt. Le moteur est
utilisé en lecture seule via `backend/engine_adapter.py`.

## Prérequis

- Windows 10/11 64 bits et WebView2 ;
- Python 3.12 ou supérieur ;
- Node.js 20 ou supérieur et npm ;
- moteur historique V1.4/V1.5 présent dans le chemin ci-dessus ;
- aucun secret ni fichier de données client n'est requis dans le dépôt.

## Installation locale

Créer un environnement Python **hors du dépôt** ou dans un dossier ignoré :

```powershell
python -m venv ..\..\.venv-webdesktop
..\..\.venv-webdesktop\Scripts\python.exe -m pip install -e ".[dev]"
```

Installer les dépendances frontend :

```powershell
cd frontend
npm ci
```

## Exécution

Backend + shell natif :

```powershell
python -m backend.desktop
```

Serveur local seul :

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Frontend de développement :

```powershell
cd frontend
npm run dev
```

## Tests

```powershell
python -m pytest backend\tests -q

cd frontend
npm run typecheck
npm test
```

Parité moteur :

```powershell
python scripts\non_regression_check.py --output ..\..\evidence\engine-parity.json
```

Préservation :

```powershell
python scripts\preservation_check.py
```

## Construction Windows

Construire d'abord le frontend :

```powershell
cd frontend
npm run build
```

Construire ensuite l'exécutable avec PyInstaller :

```powershell
cd ..
pyinstaller --noconfirm --clean `
  --distpath dist-lot2 `
  --workpath build-lot2 `
  packaging\SEGYRCALC.spec
```

Le package ainsi produit ne doit pas être commité. Les répertoires
`build-lot2/`, `dist-lot2/`, `frontend/dist/` et les exécutables sont ignorés
par Git.

## État de qualification

```text
LOT2_R6_1_ELECTRICAL_REPORTING_FIX = IMPLEMENTED_IN_ISOLATION
LOT2_R6_1_WINDOWS11_GO = PENDING
LOT2_R6_WINDOWS11_GO = PENDING
S2_WINDOWS11_GO = PENDING
G0 = PENDING
PRODUCTION_NO_GO
```

La baseline R6.1 a été validée par le propriétaire pour la mise sous gestion
Git. Aucune validation Windows 11 utilisateur, qualification poste vierge ou
autorisation de production n'est incluse.

## Sécurité

Ne jamais commiter :

- `clients.db`, bases SQLite réelles ou données clients ;
- projets confidentiels ou exports de production ;
- `.env`, jetons, clés privées et certificats ;
- `node_modules/`, `frontend/dist/`, environnements virtuels ;
- `build*/`, `dist*/`, packages PyInstaller et logs.

Le fichier `.gitignore` couvre ces exclusions.

## Documentation

- `BASELINE_R6_1.md` : contenu et preuves de la baseline ;
- `CHANGELOG.md` : historique initial ;
- `README.md` : présente installation, tests et construction.
