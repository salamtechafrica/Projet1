"""Configuration de l'API."""

import os


def _read_confidence_threshold() -> float:
    """Lit et valide le seuil de confiance depuis l'environnement."""
    raw_value = os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.7")
    try:
        threshold = float(raw_value)
    except ValueError as exc:
        raise ValueError("LOW_CONFIDENCE_THRESHOLD doit être un nombre entre 0 et 1.") from exc
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("LOW_CONFIDENCE_THRESHOLD doit être un nombre entre 0 et 1.")
    return threshold


LOW_CONFIDENCE_THRESHOLD = _read_confidence_threshold()
