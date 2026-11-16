"""Repère les champs sur lesquels le logiciel a un doute (note de projet, §3 point 4).

Chaque champ reçoit « a_verifier » (vrai/faux) et la liste des raisons, que
l'interface peut afficher en couleur. Contrôles effectués :
- champ vide ;
- date ou montant dont le format n'est pas reconnu ;
- valeur introuvable dans le texte du document (le modèle l'a peut-être inventée) ;
- valeur lue par l'OCR avec une faible confiance ;
- incohérence de calcul déclarée dans le type de document (ex : HT + TVA ≠ TTC).
"""
import re
import unicodedata
from datetime import date

from api.config import settings
from api.core.fichiers import Document

MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
        "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}

RAISON_VIDE = "absent du document ou illisible"
RAISON_DATE = "date non reconnue"
RAISON_MONTANT = "montant non reconnu"
RAISON_INTROUVABLE = "valeur introuvable dans le texte du document"
RAISON_OCR = "lecture OCR incertaine"


def simplifier(texte: str) -> str:
    """Minuscules, sans accents, espaces uniformes : pour comparer des textes."""
    texte = texte.replace("’", "'").replace("`", "'")
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", texte).strip()


def _montants(texte: str) -> list[float]:
    """Tous les nombres du texte : « 1 234,56 », « 316.50 », « 16,5 »…"""
    trouves = []
    motif = r"\d{1,3}(?:[   .]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"
    for m in re.finditer(motif, texte):
        s = re.sub(r"[   ]", "", m.group())
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")  # « 1.234.567 » : points des milliers
        try:
            trouves.append(float(s))
        except ValueError:
            pass
    return trouves


def _dates(texte: str) -> set[str]:
    """Toutes les dates du texte, au format AAAA-MM-JJ."""
    trouvees = set()
    simple = simplifier(texte)
    for j, m, a in re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b", simple):
        a = int(a) + 2000 if len(a) == 2 else int(a)
        trouvees.add(_iso(a, int(m), int(j)))
    for a, m, j in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", simple):
        trouvees.add(_iso(int(a), int(m), int(j)))
    for j, nom_mois, a in re.findall(r"\b(\d{1,2})(?:er)? (" + "|".join(MOIS) + r") (\d{4})\b", simple):
        trouvees.add(_iso(int(a), MOIS[nom_mois], int(j)))
    trouvees.discard(None)
    return trouvees


def _iso(annee: int, mois: int, jour: int) -> str | None:
    try:
        return date(annee, mois, jour).isoformat()
    except ValueError:
        return None


def valeur_dans_texte(valeur, type_champ: str, texte: str) -> bool:
    if type_champ == "montant":
        return any(abs(m - valeur) < 0.005 for m in _montants(texte))
    if type_champ == "date":
        return valeur in _dates(texte)
    return simplifier(str(valeur)) in simplifier(texte)


def _format_valide(valeur, type_champ: str) -> bool:
    if type_champ == "montant":
        return isinstance(valeur, float)
    if type_champ == "date":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(valeur))
        return bool(m) and _iso(*map(int, m.groups())) is not None
    return True


def evaluer(champs: dict, doc_type: dict, doc: Document) -> dict:
    """{nom: valeur} -> {nom: {"valeur", "a_verifier", "raisons"}}."""
    types = {c["nom"]: c["type"] for c in doc_type["champs"]}
    raisons: dict[str, list[str]] = {nom: [] for nom in champs}

    for nom, valeur in champs.items():
        type_champ = types.get(nom, "texte")
        if valeur is None:
            raisons[nom].append(RAISON_VIDE)
            continue
        if not _format_valide(valeur, type_champ):
            raisons[nom].append(RAISON_DATE if type_champ == "date" else RAISON_MONTANT)
            continue
        if doc.texte is not None and not valeur_dans_texte(valeur, type_champ, doc.texte):
            raisons[nom].append(RAISON_INTROUVABLE)
            continue
        scores = [s for t, s in doc.blocs_ocr if valeur_dans_texte(valeur, type_champ, t)]
        if scores and max(scores) < settings.seuil_doute_ocr:
            raisons[nom].append(RAISON_OCR)

    for controle in doc_type.get("controles", []):
        _verifier_somme(controle, champs, raisons)

    return {nom: {"valeur": champs[nom], "a_verifier": bool(raisons[nom]), "raisons": raisons[nom]}
            for nom in champs}


def _verifier_somme(controle: dict, champs: dict, raisons: dict) -> None:
    """Contrôle {"somme": ["montant_ht", "tva"], "total": "montant_ttc"}."""
    termes, total = controle["somme"], controle["total"]
    valeurs = [champs.get(n) for n in [*termes, total]]
    if not all(isinstance(v, float) for v in valeurs):
        return  # contrôle impossible : un des montants manque (déjà signalé)
    if abs(sum(valeurs[:-1]) - valeurs[-1]) > 0.011:
        message = f"{' + '.join(termes)} ≠ {total}"
        for n in [*termes, total]:
            raisons[n].append(message)
