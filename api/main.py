"""Entrée de l'API FastAPI pour l'extraction de documents."""

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from typing import Literal

from schemas import DocumentTypesResponse, ExtractRequest, ExtractResponse
from services.extractor import ExtractorService
from services.field_loader import FieldLoader

CONFIG_DIR = Path(__file__).parent / "config" / "document_types"
field_loader = FieldLoader(CONFIG_DIR)
extractor_service = ExtractorService()

app = FastAPI(
    title="Outil de lecture automatique de documents",
    version="0.1.0",
    description="API de squelette pour l'extraction et la vérification de documents.",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Indique que l'API est disponible."""
    return {"status": "ok"}


@app.get("/document-types", response_model=DocumentTypesResponse)
def get_document_types() -> DocumentTypesResponse:
    """Retourne les types de document définis dans les configurations YAML."""
    return DocumentTypesResponse(document_types=field_loader.list_document_types())


@app.post("/extract", response_model=ExtractResponse)
async def extract_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    model: Literal["qwen_vl", "paddleocr_vl"] = Form(...),
) -> ExtractResponse:
    """Extrait les champs d'une image envoyée en multipart/form-data."""
    request = ExtractRequest(document_type=document_type, model=model)
    try:
        fields = field_loader.load_fields(request.document_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    image = await file.read()
    if not image:
        raise HTTPException(status_code=422, detail="Le fichier envoyé est vide.")

    try:
        extracted = extractor_service.extract(
            image=image,
            fields=fields,
            model_name=request.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ExtractResponse.from_extraction(
        document_type=request.document_type,
        model=request.model,
        fields=extracted,
    )
