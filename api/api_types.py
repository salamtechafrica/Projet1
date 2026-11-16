"""Types partagés entre les extracteurs et les services."""

from typing import Any, TypedDict


class ExtractionResult(TypedDict):
    """Valeur et confiance associés à un champ extrait."""

    value: Any
    confidence: float


FieldResults = dict[str, ExtractionResult]
