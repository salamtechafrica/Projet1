"""Schémas Pydantic des configurations et réponses de l'API."""

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field

from api_types import FieldResults


class ExtractRequest(BaseModel):
    """Métadonnées de la requête multipart `POST /extract` (le fichier est séparé)."""

    document_type: str
    model: Literal["qwen_vl", "paddleocr_vl"]


class DocumentField(BaseModel):
    """Description d'un champ configurable d'un type de document."""

    name: str
    type: str
    description: str


class DocumentType(BaseModel):
    """Définition publique d'un type de document."""

    name: str
    fields: list[DocumentField]


class DocumentTypesResponse(BaseModel):
    """Réponse de `GET /document-types`."""

    document_types: list[DocumentType]


class ExtractedField(BaseModel):
    """Valeur reconnue et score de confiance associés à un champ."""

    value: Any
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractResponse(BaseModel):
    """Réponse de `POST /extract`."""

    document_type: str
    model: str
    fields: dict[str, ExtractedField]
    low_confidence_fields: list[str]

    @classmethod
    def from_extraction(
        cls,
        document_type: str,
        model: str,
        fields: FieldResults,
    ) -> "ExtractResponse":
        """Construit la réponse et marque les valeurs sous le seuil configuré."""
        from config import LOW_CONFIDENCE_THRESHOLD

        validated_fields = {
            name: ExtractedField.model_validate(result)
            for name, result in fields.items()
        }
        low_confidence_fields = [
            name for name, result in validated_fields.items()
            if result.confidence < LOW_CONFIDENCE_THRESHOLD
        ]
        return cls(
            document_type=document_type,
            model=model,
            fields=validated_fields,
            low_confidence_fields=low_confidence_fields,
        )
