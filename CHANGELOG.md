# Changelog — SEGYRCALC Web Desktop

## [0.8.0-r6.2] — 2026-11-15

### Stabilisation

- correction des messages backend doublement encodés ;
- restauration des accents dans les messages projet et source ;
- alignement des métadonnées de version sur 0.8.0-r6.2 ;
- ajout de tests de non-régression encodage et versions.

Aucune modification du moteur, du format projet, du schéma SQLite ou des
contrats API métier.

## [0.8.0-r6.1] — 2026-11-14

### Baseline Git

- création du dépôt indépendant `SEGYRCALC-WEB-DESKTOP` ;
- baseline R6.1 validée par le propriétaire pour la gestion de versions.

### Corrections R6.1

- correction du mapping P/Q des récepteurs triphasés : utilisation des
  contributions totales du moteur, et non des contributions par phase ;
- restitution de **S retenue (kVA)** et **I retenue (A)** dans le PDF
  portrait ;
- page dédiée au bilan détaillé des récepteurs ;
- largeurs, unités, alignements et pagination PDF améliorés ;
- formats numériques français : virgule décimale, regroupement des milliers,
  espace avant l'unité ;
- conservation exacte des valeurs moteur dans l'API, le XLSX et le CSV.

### Conservé

- moteurs V1.4/V1.5, formules et format projet inchangés ;
- formulaire unifié R4, suggestion de phase R5, repères Q1/Q2/Q3 ;
- création atomique Départ + Récepteur, Undo/Redo, `feeder_references` ;
- sources S2, L5.1, L5.3 et corrections Unicode.

### Qualification

```text
GIT_BASELINE_R6_1 = AUTHORIZED
GIT_REMOTE_PUSH = NOT_AUTHORIZED
LOT2_R6_1_USER_VALIDATION = ACCEPTED
LOT2_R6_1_WINDOWS11_GO = PENDING
G0 = PENDING
PRODUCTION_NO_GO
```

Aucune publication distante et aucun développement fonctionnel ne sont inclus
dans cette baseline.
