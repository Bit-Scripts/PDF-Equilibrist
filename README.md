# PDF-Equilibrist

PDF-Equilibrist est un éditeur PDF de bureau construit en Python avec PyQt6 et PyMuPDF.
Il permet de modifier, convertir, annoter, protéger et exporter des documents PDF.

## Installation

1. Créez un environnement Python compatible (`>=3.12`).
2. Installez les dépendances :

```powershell
python -m pip install -r requirements.txt
```

3. Exécutez l’application :

```powershell
python src/pdf_equilibrist/main.py
```

## Construction et packaging

- Le script NSIS d’installation se trouve dans `installer/PDF-Equilibrist.nsi`.
- Les artefacts compilés ne doivent pas être suivis dans le dépôt source.
- Les sorties de build sont ignorées par `.gitignore`.

## Documentation

La documentation source se trouve dans le dossier `docs/`.

## Licence

Ce projet est distribué sous licence MIT.
