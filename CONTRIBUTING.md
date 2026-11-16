# Contribuer

## Organisation du travail

Chaque personne développe sur sa propre branche :

- `feature/api` : modèle et API
- `feature/app` : interface
- `feature/eval` : données et évaluation
- `feature/integration` : intégration et documentation

Créez une pull request vers `main` pour chaque contribution. Personne ne pousse directement sur `main`. Faites relire et valider la pull request avant sa fusion.

## Données et confidentialité

N'ajoutez aucune vraie donnée personnelle au dépôt. Utilisez exclusivement des documents fictifs ou anonymisés. Les images privées et les documents validés doivent rester hors Git; `eval/data/images/` et `storage/` sont ignorés par Git.

## Qualité attendue

- Utilisez Python 3.11 et gardez les responsabilités séparées par dossier.
- Décrivez les champs d'un nouveau type de document dans un fichier de configuration plutôt que de coder ces champs en dur.
- Documentez toute décision qui affecte le contrat, l'architecture ou les dépendances dans `docs/decisions.md`.
- Vérifiez que l'API et l'interface démarrent avant de soumettre une pull request.
