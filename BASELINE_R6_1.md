# Baseline R6.1 — SEGYRCALC Web Desktop

## Objet

Cette baseline établit l'état de référence Git du projet
`SEGYRCALC-WEB-DESKTOP` après validation propriétaire de R6.1.

```text
Dépôt        : SEGYRCALC-WEB-DESKTOP
Version      : 0.8.0-r6.1
Branche      : main
Tag          : v0.8.0-r6.1
Date         : 2026-11-14
```

## Sources R6.1

Le dépôt contient les sources nécessaires à la reconstruction :

```text
backend/              API FastAPI, adaptation moteur, commandes projet
backend/tests/        tests backend et régression
frontend/             source React/TypeScript, tests et configuration Vite
frontend/public/      ressources graphiques et polices
packaging/            launcher, spec PyInstaller, projet exemple
scripts/              tests, parité, preservation, benchmark
installer/            source Inno Setup
pyproject.toml        dépendances et configuration Python
requirements.txt      dépendances runtime déclarées
sqlite_minimal.spec   configuration SQLite minimale
README.md             documentation de reconstruction
CHANGELOG.md          historique initial
```

## Dépendances externes

Le moteur historique n'est pas inclus dans ce dépôt. Il reste dans son
worktree d'origine :

```text
..\..\SEGYRCALC-V1.5-UI-ERGONOMIE-01\worktree\src
```

Cette dépendance est utilisée en lecture seule. Aucun fichier du dépôt
historique `D:\CALCELECT\segyr-calc` n'a été modifié.

## Validation R6.1

```text
Backend pytest       : 124 passed
Frontend vitest      : 88 passed / 20 fichiers
TypeScript           : PASS
Vite                 : PASS
PyInstaller          : PASS
Parité moteur        : all_checks_pass = true
Package              : 340 fichiers, 339/339 manifeste
Self-check package   : code 0
clients.db package   : ABSENT
```

Package de référence :

```text
D:\CALCELECT\development\SEGYRCALC-WEB-DESKTOP-DEV-01\evidence\web-08\lot2-r6-1\package\SEGYRCALC-WEB08-LOT2-R6.1
```

SHA-256 exécutable :

```text
905AD48DDDA3DB4CF32E916851BB8BA361FA65F5F7E143ACD1687A0A19AFAA03
```

## Corrections fonctionnelles incluses

- P/Q totales par récepteur, y compris pour les récepteurs triphasés ;
- S/I individuelles après Ku et Ks ;
- colonnes S/I dans le PDF portrait ;
- page dédiée et tableaux PDF lisibles ;
- formats numériques français ;
- cohérence écran / PDF / XLSX / CSV.

## Restrictions

```text
GIT_REMOTE_PUSH = NOT_AUTHORIZED
LOT2_R6_1_WINDOWS11_GO = PENDING
LOT2_R6_WINDOWS11_GO = PENDING
S2_WINDOWS11_GO = PENDING
G0 = PENDING
PRODUCTION_NO_GO
```

Cette baseline n'est pas une autorisation de production. Aucun package
PyInstaller, aucune donnée client réelle et aucun secret ne sont versionnés.

## Utilisation

```powershell
git clone <futur-depot-prive> SEGYRCALC-WEB-DESKTOP
cd SEGYRCALC-WEB-DESKTOP
python -m pytest backend\tests -q
cd frontend
npm ci
npm test
```

Les instructions complètes sont dans `README.md`.

## Prochains commits

- créer une branche de travail depuis `develop` ;
- un commit par sujet fonctionnel ou correction ;
- ne jamais pousser sur un dépôt distant sans autorisation explicite ;
- ne pas commiter de package, de base clients, de secret ou de projet réel ;
- conserver les moteurs historiques hors de ce dépôt.
