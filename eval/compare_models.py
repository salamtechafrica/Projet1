"""Compare les deux extracteurs API sur les mêmes images."""

import argparse
import json
from pathlib import Path
from typing import Any

import requests

from evaluate import evaluate_predictions

MODEL_NAMES = ("qwen_vl", "paddleocr_vl")


def main() -> None:
    """Exécute les deux modèles pour chaque image et imprime un résumé JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=Path(__file__).parent / "data" / "images")
    parser.add_argument(
        "--ground-truth-dir",
        type=Path,
        default=Path(__file__).parent / "data" / "ground_truth",
    )
    parser.add_argument("--document-type", default="invoice")
    parser.add_argument("--api-url", default="http://localhost:8000")
    args = parser.parse_args()

    predictions: dict[str, dict[str, Any]] = {model: {} for model in MODEL_NAMES}
    ground_truth = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.ground_truth_dir.glob("*.json"))
    }
    for image_path in sorted(path for path in args.images_dir.iterdir() if path.is_file()):
        for model_name in MODEL_NAMES:
            with image_path.open("rb") as image_file:
                response = requests.post(
                    f"{args.api_url.rstrip('/')}/extract",
                    files={"file": (image_path.name, image_file)},
                    data={"document_type": args.document_type, "model": model_name},
                    timeout=120,
                )
            response.raise_for_status()
            predictions[model_name][image_path.stem] = response.json()["fields"]

    metrics = evaluate_predictions(ground_truth, predictions)
    field_names = sorted({
        field_name
        for model_metrics in metrics.values()
        for field_name in model_metrics["per_field"]
    })
    print(f"{'Modèle':<16} {'Champ':<20} {'Justes / total':<16} {'Taux':>8}")
    print("-" * 64)
    for model_name, model_metrics in metrics.items():
        overall = model_metrics["overall"]
        print(
            f"{model_name:<16} {'GLOBAL':<20} "
            f"{overall['correct']} / {overall['total']:<12} {overall['accuracy']:>7.1%}"
        )
        for field_name in field_names:
            result = model_metrics["per_field"].get(field_name)
            if result is None:
                print(f"{'':<16} {field_name:<20} {'0 / 0':<16} {'n/a':>8}")
            else:
                print(
                    f"{'':<16} {field_name:<20} "
                    f"{result['correct']} / {result['total']:<12} {result['accuracy']:>7.1%}"
                )


if __name__ == "__main__":
    main()
