# Lecture automatique de documents

Photo d'un document → champs extraits automatiquement par IA → vérification humaine.

Première version : extraction des champs d'une facture.

## Prérequis

- Python 3.10 ou plus
- Git
- [Ollama](https://ollama.com/download), ou en terminal : `winget install Ollama.Ollama`
- Environ 10 Go d'espace disque libre

## Installation (Windows)

```powershell
git clone https://github.com/salamtechafrica/Projet1.git
cd Projet1

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
ollama pull qwen2.5vl:7b
```

**PC modeste** (pas de carte graphique NVIDIA ou moins de 16 Go de RAM) : utilisez
`ollama pull qwen2.5vl:3b` et mettez `MODEL_NAME=qwen2.5vl:3b` dans `.env`.

## Lancer l'API

```powershell
.venv\Scripts\Activate.ps1
uvicorn api.main:app --reload
```

- Santé de l'API : http://localhost:8000/health
- Documentation et tests interactifs : http://localhost:8000/docs

## Tester

**Tests automatiques** (sans le modèle, à lancer avant chaque push) :
```powershell
pytest
```

**Extraire un document** (API lancée), en choisissant son type :
```powershell
curl.exe -F "fichier=@chemin\vers\facture.jpg" http://localhost:8000/extract/facture
```
- Types disponibles : http://localhost:8000/types (`facture`, `avis_echeance`…)
- Formats acceptés : images (JPEG, PNG, WebP, HEIC, TIFF…) et PDF.
- Chaque champ revient avec sa valeur et un indicateur `a_verifier` (champ à afficher en
  couleur) avec ses raisons. **Format complet de la réponse : [docs/format_api.md](docs/format_api.md).**

### Les deux approches à comparer

| Approche | Réglage | Principe |
| --- | --- | --- |
| Vision | `APPROCHE=vision` | Qwen-VL lit l'image et renvoie les champs (une étape) |
| OCR puis modèle | `APPROCHE=ocr` | Un OCR lit le texte, puis Qwen range les informations |

Pour l'OCR, deux moteurs : `OCR_MOTEUR=rapidocr` (léger, tourne sur tout PC) ou
`OCR_MOTEUR=paddleocr_vl` (celui du plan ; Python 3.8-3.12 et GPU conseillé, voir Colab).
On peut aussi choisir l'approche à chaque requête : `/extract/facture?approche=vision`.

Un PDF qui contient déjà du texte (généré par un logiciel) est lu directement, quelle que
soit l'approche. Au premier lancement, les modèles OCR (~20 Mo) sont téléchargés.

### Sur Google Colab (GPU gratuit)

Sans carte graphique, une extraction prend ~1 min. Pour mesurer les vraies performances
et tester Qwen-VL 7b et PaddleOCR-VL : notebook [colab/Projet1_colab.ipynb](colab/Projet1_colab.ipynb)
(documents fictifs uniquement).

**Mesurer la précision** : script d'évaluation à venir dans `eval/` (rôle Données et évaluation).

## Structure

```
api/
  main.py              points d'entrée de l'API
  config.py            réglages (lus depuis .env)
  core/fichiers.py     reconnaissance du format (image, PDF) et préparation
  core/ocr.py          lecture du texte des images (RapidOCR ou PaddleOCR-VL)
  core/extraction.py   appel au modèle IA
  core/controles.py    repérage des champs douteux
  document_types/      description de chaque type de document (JSON)
eval/                  évaluation de la précision
tests/                 tests automatiques
docs/                  notes et décisions (dont le format de l'API)
colab/                 notebook pour tester sur GPU
```

**Ajouter un type de document** : créer un fichier JSON dans `api/document_types/`
sur le modèle de `facture.json`. Aucun code à modifier. Soigner :
- la `description` de chaque champ : c'est ce que lit le modèle pour savoir quoi chercher ;
- `controles` (facultatif) : vérifications de calcul, ex. HT + TVA = TTC.

## Règles de travail

- Une branche par fonctionnalité, fusion par pull request
- Jamais de push direct sur `main`
- Lancer `pytest` avant chaque push
- Aucun vrai document ni aucun secret dans le dépôt (le `.env` et les images sont ignorés)

## Problèmes fréquents

| Problème | Solution |
| --- | --- |
| `ollama` n'est pas reconnu | Fermer et rouvrir VS Code après l'installation d'Ollama |
| Erreur à l'activation de `.venv` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Erreur 500 sur `/extract/...` | Vérifier qu'Ollama tourne et que le modèle du `.env` est téléchargé (`ollama list`) |
| Extraction très lente | Normal sans carte graphique (~1 min). Garder `qwen2.5vl:3b` et `APPROCHE=ocr`, ou tester sur Colab |
| Erreur 503 | Le moteur OCR demandé n'est pas installé : `OCR_MOTEUR=rapidocr` ou utiliser Colab |