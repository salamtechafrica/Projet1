# Données et évaluation

Les images de test doivent être fictives ou anonymisées. Un fichier JSON de référence par document est attendu dans `data/ground_truth/`; associez-le à l'image par son nom de base. Ne placez aucune donnée personnelle réelle dans Git.

`evaluate.py` compare les valeurs prédites avec les réponses de référence et calcule les taux par champ et globalement. `compare_models.py` envoie chaque image aux deux modèles via l'API puis affiche les taux comparatifs. Il attend un JSON de référence par image dans `data/ground_truth/`, avec les champs attendus au premier niveau, par exemple `{"fournisseur": "ACME SARL"}`.

Les images et sorties locales sont ignorées par Git. Les modèles et dépendances lourdes ne sont pas installés dans ce squelette.
