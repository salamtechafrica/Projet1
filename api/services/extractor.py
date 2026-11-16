"""Sélection de l'extracteur de modèle."""

from api_types import ExtractionResult
from models.base import BaseExtractor
from models.paddleocr_vl import PaddleOCRVLExtractor
from models.qwen_vl import QwenVLExtractor
from schemas import DocumentField


class ExtractorService:
    """Sélectionne un extracteur par identifiant et lui transmet l'image."""

    def __init__(self) -> None:
        self._extractors: dict[str, BaseExtractor] = {
            "qwen_vl": QwenVLExtractor(),
            "paddleocr_vl": PaddleOCRVLExtractor(),
        }

    def extract(
        self,
        image: bytes,
        fields: list[DocumentField],
        model_name: str,
    ) -> ExtractionResult:
        """Exécute le modèle choisi ou lève une erreur pour un identifiant inconnu."""
        extractor = self._extractors.get(model_name)
        if extractor is None:
            choices = ", ".join(sorted(self._extractors))
            raise ValueError(f"Modèle inconnu : {model_name}. Choix disponibles : {choices}")
        return extractor.extract(image=image, fields=fields)
