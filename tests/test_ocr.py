import io
import math

import pytest
from PIL import Image, ImageDraw, ImageFont

from api.config import settings
from api.core.fichiers import preparer_document
from api.core.ocr import reconstituer_lignes


def _boite(x, y, largeur, hauteur=20, angle_deg=0.0):
    """Boîte OCR (4 coins) d'un texte placé en (x, y), éventuellement inclinée."""
    a = math.radians(angle_deg)
    coins = [(0, 0), (largeur, 0), (largeur, hauteur), (0, hauteur)]
    return [[x + cx * math.cos(a) - cy * math.sin(a), y + cx * math.sin(a) + cy * math.cos(a)]
            for cx, cy in coins]


def test_lignes_remises_dans_lordre():
    boites = [_boite(400, 100, 150), _boite(50, 100, 120), _boite(50, 40, 300)]
    textes = ["316,50 EUR", "Total TTC", "FACTURE"]
    assert reconstituer_lignes(boites, textes) == "FACTURE\nTotal TTC\t316,50 EUR"


def test_photo_inclinee_garde_les_lignes():
    # Photo penchée de 4° : l'étiquette et le montant ne sont pas à la même hauteur
    # en pixels, mais doivent rester sur la même ligne.
    a = math.radians(4)
    def place(x, y, largeur, t):
        return _boite(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), largeur,
                      angle_deg=4), t
    elements = [place(50, 100, 120, "Total HT"), place(600, 100, 150, "300,00 EUR"),
                place(50, 140, 120, "Total TTC"), place(600, 140, 150, "316,50 EUR")]
    texte = reconstituer_lignes([e[0] for e in elements], [e[1] for e in elements])
    assert texte == "Total HT\t300,00 EUR\nTotal TTC\t316,50 EUR"


def _facture_jpeg():
    img = Image.new("RGB", (2480, 3508), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 42)
    except OSError:
        pytest.skip("police Arial absente")
    y = 200
    for gauche, droite in [("SARL Boulangerie Dupont", ""), ("FACTURE N° FA-2026-0142", ""),
                           ("Date : 03/10/2026", ""), ("Total HT", "300,00 EUR"),
                           ("TVA 5,5 %", "16,50 EUR"), ("Total TTC", "316,50 EUR")]:
        d.text((200, y), gauche, fill="black", font=f)
        d.text((1700, y), droite, fill="black", font=f)
        y += 80
    sortie = io.BytesIO()
    img.save(sortie, "JPEG", quality=90)
    return sortie.getvalue()


def test_facture_lue_par_ocr():
    doc = preparer_document(_facture_jpeg(), "ocr")
    assert doc.source == "image_ocr"
    assert doc.images == []
    assert "FA-2026-0142" in doc.texte
    assert "Total TTC\t316,50 EUR" in doc.texte
    # les morceaux lus et leur confiance sont gardés pour signaler les champs douteux
    assert any("316,50" in t and 0 < s <= 1 for t, s in doc.blocs_ocr)


def test_approche_vision_envoie_limage():
    doc = preparer_document(_facture_jpeg(), "vision")
    assert doc.source == "image_vision"
    assert len(doc.images) == 1
    assert doc.texte is None


def test_approche_par_defaut_du_reglage(monkeypatch):
    monkeypatch.setattr(settings, "approche", "vision")
    assert preparer_document(_facture_jpeg()).source == "image_vision"


def test_paddleocr_vl_absent_message_clair(monkeypatch):
    import builtins
    from api.core import ocr
    ocr._paddleocr_vl.cache_clear()
    vrai_import = builtins.__import__

    def import_sans_paddle(nom, *args, **kwargs):
        if nom == "paddleocr":
            raise ImportError("absent")
        return vrai_import(nom, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", import_sans_paddle)
    with pytest.raises(ocr.MoteurIndisponible, match="Python 3.8 à 3.12"):
        ocr.lire_texte(b"jpeg", "paddleocr_vl")
    ocr._paddleocr_vl.cache_clear()
