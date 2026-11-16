"""Chargement et validation des définitions de champs YAML."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from schemas import DocumentField, DocumentType


class FieldLoader:
    """Charge les types de document depuis un répertoire de configuration."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def list_document_types(self) -> list[DocumentType]:
        """Charge toutes les configurations YAML du répertoire."""
        return [self._load_document_type(path) for path in sorted(self.config_dir.glob("*.yaml"))]

    def load_fields(self, document_type: str) -> list[DocumentField]:
        """Retourne les champs d'un type; lève FileNotFoundError s'il est inconnu."""
        path = next(
            (candidate for candidate in self.config_dir.glob("*.yaml")
             if candidate.stem == document_type),
            None,
        )
        if path is None:
            raise FileNotFoundError(f"Type de document inconnu : {document_type}")
        return self._load_document_type(path).fields

    @staticmethod
    def _load_document_type(path: Path) -> DocumentType:
        """Parse et valide un fichier de configuration."""
        with path.open("r", encoding="utf-8") as config_file:
            data: Any = yaml.safe_load(config_file)
        try:
            return DocumentType.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Configuration de document invalide : {path.name}") from exc
