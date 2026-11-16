"""Calcul des taux de champs correctement extraits."""

import argparse
import json
from pathlib import Path
from typing import Any


def normalize(value: Any) -> str:
    """Normalise les valeurs pour une comparaison exacte sans espaces périphériques."""
    return "" if value is None else str(value).strip().casefold()


def evaluate_predictions(
    ground_truth: dict[str, dict[str, Any]],
    predictions: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Calcule les taux par champ et global pour chaque modèle.

    `ground_truth` associe un identifiant de document à ses champs. `predictions`
    associe un modèle, puis un document, à une réponse d'extraction.
    """
    metrics: dict[str, dict[str, Any]] = {}
    for model_name, documents in predictions.items():
        field_counts: dict[str, list[int]] = {}
        total_correct = 0
        total_fields = 0
        for document_id, expected_fields in ground_truth.items():
            actual_fields = documents.get(document_id, {})
            for field_name, expected in expected_fields.items():
                counts = field_counts.setdefault(field_name, [0, 0])
                actual = actual_fields.get(field_name)
                if isinstance(actual, dict):
                    actual = actual.get("value")
                counts[1] += 1
                total_fields += 1
                if normalize(actual) == normalize(expected):
                    counts[0] += 1
                    total_correct += 1
        metrics[model_name] = {
            "per_field": {
                name: {"correct": counts[0], "total": counts[1], "accuracy": counts[0] / counts[1]}
                for name, counts in sorted(field_counts.items())
            },
            "overall": {
                "correct": total_correct,
                "total": total_fields,
                "accuracy": total_correct / total_fields if total_fields else 0.0,
            },
        }
    return metrics


def main() -> None:
    """Charge deux fichiers JSON d'évaluation et imprime les métriques."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True, help="JSON document_id -> champs")
    parser.add_argument("--predictions", type=Path, required=True, help="JSON modèle -> document_id -> champs")
    args = parser.parse_args()
    ground_truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    print(json.dumps(evaluate_predictions(ground_truth, predictions), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
