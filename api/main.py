"""API de lecture automatique de documents. Format des réponses : docs/format_api.md."""
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from api.config import settings
from api.core.extraction import ReponseModeleInvalide, extraire, lister_types
from api.core.fichiers import FormatNonSupporte
from api.core.ocr import MoteurIndisponible

app = FastAPI(title="Lecture automatique de documents")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/types")
def types():
    """Types de documents disponibles et leurs champs (pour la liste de choix de l'interface)."""
    return [{"type": t["type"], "description": t["description"],
             "champs": [{"nom": c["nom"], "type": c["type"], "description": c["description"]}
                        for c in t["champs"]]}
            for t in lister_types()]


# Fonction « def » (et non « async def ») : FastAPI l'exécute dans un fil séparé, donc
# une extraction longue ne bloque pas les autres requêtes.
@app.post("/extract/{type_doc}")
def extract(type_doc: str, fichier: UploadFile = File(...),
            approche: Literal["vision", "ocr"] | None = Query(
                None, description="« vision » : Qwen-VL lit l'image ; « ocr » : lecture du texte "
                                  "puis Qwen range les champs. Vide = réglage APPROCHE du .env.")):
    """Extrait les champs d'un document dont l'utilisateur a choisi le type."""
    taille_max = settings.taille_max_mo * 1024 * 1024
    contenu = fichier.file.read(taille_max + 1)
    if len(contenu) > taille_max:
        raise HTTPException(status_code=413, detail=f"Fichier trop gros (maximum {settings.taille_max_mo} Mo).")
    try:
        return extraire(contenu, type_doc, approche)
    except FormatNonSupporte as e:
        raise HTTPException(status_code=415, detail=str(e))
    except MoteurIndisponible as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ReponseModeleInvalide as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
