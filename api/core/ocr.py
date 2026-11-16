"""Lecture du texte d'une image par OCR (reconnaissance de caractères), en local.

Deux moteurs au choix (réglage OCR_MOTEUR) :
- rapidocr     : modèles PP-OCRv5 (famille PaddleOCR) au format ONNX ; léger, tourne
                 sur n'importe quel PC (~3 s par page sans carte graphique) ;
- paddleocr_vl : PaddleOCR-VL, prévu par la note de projet ; lit aussi tableaux et mises
                 en page complexes ; demande Python 3.8-3.12 et de préférence un GPU.
"""
import math
import os
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from statistics import median

from api.config import settings


class MoteurIndisponible(Exception):
    """Le moteur OCR demandé n'est pas installé sur cette machine."""


@dataclass
class ResultatOCR:
    texte: str
    score_moyen: float | None  # confiance moyenne (0 à 1) ; None si le moteur n'en donne pas
    nb_caracteres: int
    # Morceaux de texte lus et leur confiance : sert à signaler les champs douteux.
    blocs: list[tuple[str, float]] = field(default_factory=list)


def lire_texte(image_jpeg: bytes, moteur: str | None = None) -> ResultatOCR:
    moteur = moteur or settings.ocr_moteur
    if moteur == "paddleocr_vl":
        return _lire_paddleocr_vl(image_jpeg)
    return _lire_rapidocr(image_jpeg)


# --- RapidOCR ---

@lru_cache(maxsize=1)
def _rapidocr():
    # Chargement différé : quelques secondes, une seule fois.
    # Au tout premier lancement, les modèles OCR (~20 Mo) sont téléchargés.
    from rapidocr import RapidOCR, LangRec, OCRVersion, ModelType
    return RapidOCR(params={
        "Rec.lang_type": LangRec.LATIN,  # français, accents, etc.
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE,
        "Det.ocr_version": OCRVersion.PPOCRV5,
        "Det.model_type": ModelType.MOBILE,
    })


def _lire_rapidocr(image_jpeg: bytes) -> ResultatOCR:
    res = _rapidocr()(image_jpeg)
    if not res.txts:
        return ResultatOCR(texte="", score_moyen=0.0, nb_caracteres=0)
    return ResultatOCR(
        texte=reconstituer_lignes(list(res.boxes), list(res.txts)),
        score_moyen=sum(res.scores) / len(res.scores),
        nb_caracteres=sum(len(t) for t in res.txts),
        blocs=list(zip(res.txts, (float(s) for s in res.scores))),
    )


# --- PaddleOCR-VL ---

@lru_cache(maxsize=1)
def _paddleocr_vl():
    # Attention : PaddleOCR refuse d'être initialisé deux fois dans le même processus.
    # Après un échec ici, il faut redémarrer Python avant de réessayer.
    try:
        from paddleocr import PaddleOCRVL
        return PaddleOCRVL()
    except ImportError as e:
        raise MoteurIndisponible(
            f"PaddleOCR-VL n'est pas installé ou ne se charge pas ({type(e).__name__} : {e}). "
            "Il demande Python 3.8 à 3.12 et de préférence un GPU. "
            "Sinon : OCR_MOTEUR=rapidocr."
        ) from e


def _lire_paddleocr_vl(image_jpeg: bytes) -> ResultatOCR:
    pipeline = _paddleocr_vl()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(image_jpeg)
        chemin = f.name
    try:
        textes = []
        for res in pipeline.predict(chemin):
            md = res.markdown  # texte de la page mis en forme (titres, tableaux…)
            textes.append(md.get("markdown_texts", "") if isinstance(md, dict) else str(md))
    finally:
        os.unlink(chemin)
    texte = "\n".join(textes).strip()
    # PaddleOCR-VL ne donne pas de score de confiance par morceau de texte.
    return ResultatOCR(texte=texte, score_moyen=None, nb_caracteres=len(texte))


# --- Remise en ordre du texte (RapidOCR) ---

def reconstituer_lignes(boites, textes) -> str:
    """Remet les morceaux de texte dans l'ordre de lecture, ligne par ligne.

    L'OCR renvoie des blocs dans un ordre quelconque ; or pour une facture il est
    essentiel que « Total TTC » et « 316,50 EUR » se retrouvent sur la même ligne.
    Chaque boîte = 4 coins [haut-gauche, haut-droit, bas-droit, bas-gauche].
    """
    # 1) Inclinaison de la photo : angle médian des bords supérieurs des boîtes.
    angle = median(math.atan2(b[1][1] - b[0][1], b[1][0] - b[0][0]) for b in boites)
    cos, sin = math.cos(-angle), math.sin(-angle)

    blocs = []
    for b, t in zip(boites, textes):
        cx = sum(p[0] for p in b) / 4
        cy = sum(p[1] for p in b) / 4
        # coordonnées « redressées » : on annule l'inclinaison
        x = cx * cos - cy * sin
        y = cx * sin + cy * cos
        largeur = math.dist(b[0], b[1])
        hauteur = math.dist(b[0], b[3])
        blocs.append({"x": x - largeur / 2, "fin": x + largeur / 2, "y": y, "h": hauteur, "t": t})

    # 2) Regroupement en lignes : même hauteur à une demi-ligne près.
    h_med = median(b["h"] for b in blocs)
    lignes: list[list[dict]] = []
    for bloc in sorted(blocs, key=lambda b: b["y"]):
        if lignes and abs(bloc["y"] - lignes[-1][-1]["y"]) < h_med * 0.5:
            lignes[-1].append(bloc)
        else:
            lignes.append([bloc])

    # 3) Dans chaque ligne, de gauche à droite ; un grand écart devient une tabulation
    #    pour garder la notion de colonnes (tableaux des factures).
    sortie = []
    for ligne in lignes:
        ligne.sort(key=lambda b: b["x"])
        morceaux = [ligne[0]["t"]]
        for avant, bloc in zip(ligne, ligne[1:]):
            morceaux.append("\t" if bloc["x"] - avant["fin"] > h_med * 1.5 else " ")
            morceaux.append(bloc["t"])
        sortie.append("".join(morceaux))
    return "\n".join(sortie)
