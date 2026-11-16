"""Transforme n'importe quel fichier reçu en quelque chose que le modèle sait lire.

Formats acceptés (reconnus d'après le contenu du fichier, pas son nom) :
- images : JPEG, PNG, WebP, BMP, TIFF, GIF, HEIC/HEIF (photos d'iPhone)…
- PDF : on lit directement le texte s'il y en a (PDF généré par un logiciel),
  sinon on convertit les pages en images (PDF scanné).

Les images (photos, pages scannées) sont ensuite traitées selon l'approche choisie :
- "vision" : envoyées telles quelles au modèle Qwen-VL ;
- "ocr"    : leur texte est lu par OCR ; si l'OCR échoue (trop peu de texte, faible
             confiance), on se rabat sur la vision.
"""
import io
from dataclasses import dataclass, field

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from api.config import settings
from api.core.ocr import lire_texte

register_heif_opener()  # permet à Pillow d'ouvrir les HEIC comme n'importe quelle image

# En dessous de ce nombre de caractères par page, le texte est jugé inexploitable
# (PDF considéré comme scanné, ou lecture OCR ratée).
MIN_CARACTERES_PAR_PAGE = 30

FORMATS_ACCEPTES = "images (JPEG, PNG, WebP, HEIC, TIFF…) ou PDF"


class FormatNonSupporte(Exception):
    """Le fichier envoyé n'est ni une image lisible ni un PDF lisible."""


@dataclass
class Document:
    """Contenu prêt à envoyer au modèle : du texte, ou des images (en JPEG)."""
    images: list[bytes] = field(default_factory=list)
    texte: str | None = None
    # Comment le contenu a été obtenu : "pdf_texte", "image_ocr", "image_vision",
    # "pdf_scanne_ocr" ou "pdf_scanne_vision".
    source: str = ""
    # Morceaux de texte lus par l'OCR et leur confiance (sert à signaler les champs douteux).
    blocs_ocr: list[tuple[str, float]] = field(default_factory=list)


def preparer_document(contenu: bytes, approche: str | None = None) -> Document:
    approche = approche or settings.approche
    if contenu.startswith(b"%PDF"):
        return _depuis_pdf(contenu, approche)
    return _texte_ou_images([preparer_image(contenu)], "image", approche)


def _texte_ou_images(images: list[bytes], origine: str, approche: str) -> Document:
    """Approche « ocr » : lit le texte de chaque image ; si une page est mal lue, garde les images."""
    if approche == "ocr":
        resultats = [lire_texte(img) for img in images]
        if all(r.nb_caracteres >= MIN_CARACTERES_PAR_PAGE
               and (r.score_moyen is None or r.score_moyen >= settings.ocr_score_min)
               for r in resultats):
            return Document(texte=_assembler_pages([r.texte for r in resultats]),
                            source=f"{origine}_ocr",
                            blocs_ocr=[b for r in resultats for b in r.blocs])
    return Document(images=images, source=f"{origine}_vision")


def _assembler_pages(textes: list[str]) -> str:
    if len(textes) == 1:
        return textes[0]
    return "\n\n".join(f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(textes))


def preparer_image(image: bytes, max_px: int | None = None) -> bytes:
    """Redresse, réduit et convertit une image en JPEG."""
    max_px = max_px or settings.image_max_px
    try:
        img = Image.open(io.BytesIO(image))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise FormatNonSupporte(
            f"Format de fichier non pris en charge. Formats acceptés : {FORMATS_ACCEPTES}."
        ) from e
    return _en_jpeg(ImageOps.exif_transpose(img), max_px)


def _en_jpeg(img: Image.Image, max_px: int) -> bytes:
    img = img.convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)  # ne fait rien si déjà plus petite
    sortie = io.BytesIO()
    img.save(sortie, format="JPEG", quality=90)
    return sortie.getvalue()


def _depuis_pdf(contenu: bytes, approche: str) -> Document:
    try:
        pdf = pdfium.PdfDocument(contenu)
    except pdfium.PdfiumError as e:
        raise FormatNonSupporte("Le PDF est illisible, protégé par mot de passe ou abîmé.") from e

    try:
        pages = [pdf[i] for i in range(min(len(pdf), settings.pdf_max_pages))]
        if not pages:
            raise FormatNonSupporte("Le PDF ne contient aucune page.")

        # 1) PDF généré par un logiciel : le texte exact est déjà là, on le lit directement
        #    (quelle que soit l'approche : c'est plus fiable que toute lecture d'image).
        textes = [p.get_textpage().get_text_range().strip() for p in pages]
        if sum(len(t) for t in textes) >= MIN_CARACTERES_PAR_PAGE * len(pages):
            return Document(texte=_assembler_pages(textes), source="pdf_texte")

        # 2) PDF scanné : on transforme chaque page en image, puis OCR ou vision.
        images = []
        for page in pages:
            largeur, hauteur = page.get_size()  # en points (1/72 de pouce)
            echelle = settings.image_max_px / max(largeur, hauteur)
            img = page.render(scale=echelle).to_pil()
            images.append(_en_jpeg(img, settings.image_max_px))
        return _texte_ou_images(images, "pdf_scanne", approche)
    finally:
        pdf.close()
