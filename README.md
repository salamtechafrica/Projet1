# Outil de lecture automatique de documents

Squelette d'un outil qui extrait les champs de documents photographiés, les fait vérifier par une personne, puis prépare leur enregistrement et leur export. Le premier type pris en charge est la facture. Les deux extracteurs sont actuellement des stubs qui renvoient des valeurs factices.

## Équipe et dossiers

| Responsable | Dossiers | Mission |
| --- | --- | --- |
| Modèle et API | `api/` | Contrat API, configuration des champs et intégration des extracteurs |
| Interface | `app/` | Import de photo, correction et validation utilisateur |
| Données et évaluation | `eval/` | Jeux anonymisés et comparaison des résultats |
| Intégration | `docs/`, `storage/`, racine | Intégration, décisions et stockage des documents validés |

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le processus de contribution.

## Lancer avec Docker

Depuis la racine du dépôt :

```shell
docker compose up --build
```

L'API est disponible à `http://localhost:8000` et l'interface à `http://localhost:8501`.

## Lancer sans Docker

Python 3.11 est requis. Dans Windows PowerShell, ouvrez deux terminaux depuis la racine du dépôt.

Terminal API :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r api\requirements.txt
python -m uvicorn main:app --app-dir api --reload --host 0.0.0.0 --port 8000
```

Terminal interface :

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r app\requirements.txt
$env:API_URL = "http://localhost:8000"
python -m streamlit run app\streamlit_app.py
```

Pour ouvrir l'interface, accédez ensuite à `http://localhost:8501`. Dans un terminal PowerShell supplémentaire, l'évaluation peut être lancée après activation de `.venv` et installation de `eval\requirements.txt` :

```powershell
python eval\compare_models.py --images-dir eval\data\images --ground-truth-dir eval\data\ground_truth
```

Pour les autres systèmes, activez `.venv` avec la commande correspondante à votre shell puis utilisez les mêmes commandes `pip`, `uvicorn` et `streamlit`.

## Vérification rapide

- `GET http://localhost:8000/health` vérifie l'API.
- `GET http://localhost:8000/document-types` liste les types configurés.
- L'interface permet de sélectionner une image, un type et un modèle puis de préremplir les champs avec les données factices.
- Le seuil de confiance par défaut est `0.7` et peut être réglé avec `LOW_CONFIDENCE_THRESHOLD`.

Les modèles lourds ne sont pas téléchargés ni installés dans ce squelette. Les documents et données réels ne doivent jamais être ajoutés au dépôt.
