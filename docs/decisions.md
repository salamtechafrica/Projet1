# Journal des décisions

| Date | Décision | Motif / conséquences |
| --- | --- | --- |
| 2026-11-16 | Python 3.11, FastAPI, Pydantic v2 et Streamlit forment la base du squelette. | Respecte les contraintes du projet et permet à l'interface d'avancer sur l'API factice. |
| 2026-11-16 | Les champs sont décrits dans des fichiers YAML séparés du code. | L'ajout d'un type de document ne doit pas nécessiter de modifier l'extracteur. |
| 2026-11-16 | Qwen-VL et PaddleOCR-VL partagent le contrat `BaseExtractor`. | Permet de comparer les modèles avec le même schéma d'entrée et de sortie. |
| 2026-11-16 | Seuil de confiance configurable par `LOW_CONFIDENCE_THRESHOLD`, défaut `0.7`. | Permet d'ajuster le signalement sans modifier le code. |
| 2026-11-16 | Les données privées et les modèles téléchargés sont exclus de Git. | Évite d'exposer des documents personnels et des fichiers volumineux. |
