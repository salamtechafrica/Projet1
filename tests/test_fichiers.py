import io

import pytest
from PIL import Image

from api.core.fichiers import FormatNonSupporte, preparer_document, preparer_image


def _image(largeur, hauteur, fmt="PNG", mode="RGB"):
    sortie = io.BytesIO()
    Image.new(mode, (largeur, hauteur), "white").save(sortie, format=fmt)
    return sortie.getvalue()


def _pdf_avec_texte(texte):
    """PDF minimal contenant du vrai texte, comme une facture générée par un logiciel."""
    flux = f"BT /F1 24 Tf 72 700 Td ({texte}) Tj ET".encode()
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf, positions = b"%PDF-1.4\n", []
    for i, obj in enumerate(objets, 1):
        positions.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % p for p in positions)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objets) + 1, xref)
    return pdf


def _pdf_scanne(nb_pages):
    """PDF ne contenant que des images, comme un document passé au scanner."""
    pages = [Image.new("RGB", (2480, 3508), "white") for _ in range(nb_pages)]
    sortie = io.BytesIO()
    pages[0].save(sortie, format="PDF", save_all=True, append_images=pages[1:])
    return sortie.getvalue()


# --- Images ---

def test_grande_image_est_reduite():
    resultat = Image.open(io.BytesIO(preparer_image(_image(4000, 3000), max_px=1280)))
    assert resultat.size == (1280, 960)  # proportions conservées
    assert resultat.format == "JPEG"


def test_petite_image_pas_agrandie():
    resultat = Image.open(io.BytesIO(preparer_image(_image(800, 600), max_px=1280)))
    assert resultat.size == (800, 600)


@pytest.mark.parametrize("fmt,mode", [("PNG", "RGBA"), ("WEBP", "RGB"), ("BMP", "RGB"),
                                      ("TIFF", "RGB"), ("GIF", "P"), ("HEIF", "RGB")])
def test_formats_image_acceptes(fmt, mode):
    doc = preparer_document(_image(500, 400, fmt=fmt, mode=mode))
    # image blanche : l'OCR ne trouve rien, on garde l'image pour le modèle de vision
    assert doc.source == "image_vision"
    assert len(doc.images) == 1
    assert Image.open(io.BytesIO(doc.images[0])).mode == "RGB"


# --- PDF ---

def test_pdf_avec_texte_lu_directement():
    doc = preparer_document(_pdf_avec_texte("Facture FA-2026-0142 Total TTC 316,50 EUR"))
    assert doc.source == "pdf_texte"
    assert "FA-2026-0142" in doc.texte
    assert doc.images == []


def test_pdf_scanne_converti_en_images():
    doc = preparer_document(_pdf_scanne(2))
    assert doc.source == "pdf_scanne_vision"  # pages blanches : rien à lire par OCR
    assert len(doc.images) == 2
    assert max(Image.open(io.BytesIO(doc.images[0])).size) == 1280


def test_pdf_limite_au_nombre_max_de_pages():
    doc = preparer_document(_pdf_scanne(5))
    assert len(doc.images) == 3


def test_pdf_abime_refuse():
    with pytest.raises(FormatNonSupporte):
        preparer_document(b"%PDF-1.4 n'importe quoi")


# --- Autres formats ---

@pytest.mark.parametrize("contenu", [b"ceci n'est pas une image", b"", b"PK\x03\x04 un zip"])
def test_format_inconnu_refuse(contenu):
    with pytest.raises(FormatNonSupporte):
        preparer_document(contenu)
