"""Extraction des champs d'un document par le modèle IA (Qwen-VL via Ollama).

L'utilisateur choisit le type de document ; le modèle remplit les champs de ce type ;
chaque champ est ensuite contrôlé pour signaler ceux qui sont douteux (controles.py).
Format de la réponse : docs/format_api.md.
"""
import json
import re
import time
from pathlib import Path

import ollama

from api.config import settings
from api.core.controles import evaluer
from api.core.fichiers import Document, preparer_document

VERSION_FORMAT = 1  # à incrémenter si le format de réponse change
TYPES_DIR = Path(__file__).parent.parent / "document_types"

# Types JSON autorisés au modèle pour chaque type de champ. Les montants peuvent arriver
# en texte (« 300,00 EUR ») : les forcer en nombre pousse le modèle à répondre null.
TYPES_JSON = {"texte": ["string"], "date": ["string"], "montant": ["number", "string"]}


class ReponseModeleInvalide(Exception):
    """Le modèle n'a pas renvoyé un JSON valide."""


def charger_type(nom: str) -> dict:
    chemin = TYPES_DIR / f"{nom}.json"
    if not re.fullmatch(r"[a-z0-9_]+", nom) or not chemin.exists():
        raise ValueError(f"Type de document inconnu : {nom}")
    return json.loads(chemin.read_text(encoding="utf-8"))


def lister_types() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TYPES_DIR.glob("*.json"))]


# --- Ce qu'on envoie au modèle ---

def construire_prompt(doc_type: dict) -> str:
    champs = "\n".join(f"- {c['nom']} : {c['description']}" for c in doc_type["champs"])
    return (
        f"Extrais les informations de ce document ({doc_type['description']}).\n\n"
        f"Champs à remplir dans « champs » :\n{champs}\n\n"
        "Règles :\n"
        "- Recopie les textes exactement comme ils sont écrits dans le document "
        "(mêmes majuscules, mêmes espaces, mêmes accents).\n"
        "- Montants : nombres sans espace ni séparateur de milliers, avec un point pour les "
        "décimales (491,72 € devient 491.72 ; 148.750 FCFA ou 148 750 FCFA devient 148750).\n"
        "- Dates : format AAAA-MM-JJ.\n"
        "- Si une information est absente ou illisible, mets null. Ne la remplace jamais "
        "par une autre information qui lui ressemble."
    )


def construire_schema(doc_type: dict) -> dict:
    """Structure imposée à la réponse du modèle : toujours les mêmes champs."""
    champs = {c["nom"]: {"type": [*TYPES_JSON[c["type"]], "null"]} for c in doc_type["champs"]}
    return {
        "type": "object",
        "properties": {"champs": {"type": "object", "properties": champs, "required": list(champs)}},
        "required": ["champs"],
    }


def construire_message(doc: Document, consigne: str) -> dict:
    if doc.texte is not None:
        return {"role": "user",
                "content": f"Document (les tabulations séparent les colonnes) :\n{doc.texte}\n\n{consigne}"}
    return {"role": "user", "content": consigne, "images": doc.images}


# --- Nettoyage des valeurs renvoyées par le modèle ---

def est_vide(valeur) -> bool:
    """None, '' ou le mot « null » écrit en texte par le modèle."""
    return valeur is None or (isinstance(valeur, str) and valeur.strip().lower() in ("", "null", "none"))


def normaliser_date(valeur):
    """'03/10/2026' -> '2026-10-03'. Laisse la valeur telle quelle si non reconnue."""
    if not isinstance(valeur, str):
        return valeur
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", valeur.strip())
    if m:
        jour, mois, annee = m.groups()
        return f"{annee}-{int(mois):02d}-{int(jour):02d}"
    return valeur.strip()


def normaliser_montant(valeur):
    """'1 234,56 €' -> 1234.56 ; '148.750 FCFA' -> 148750. Laisse tel quel si non reconnu."""
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return float(valeur)
    if not isinstance(valeur, str):
        return valeur
    s = re.sub(r"[^\d,.\-]", "", valeur)
    if "," in s and "." in s:  # le dernier séparateur est la décimale
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(".") > 1 or s.count(",") > 1:  # « 1.487.500 » : séparateurs de milliers
        s = s.replace(".", "").replace(",", "")
    elif re.fullmatch(r"-?[1-9]\d{0,2}[.,]\d{3}", s):
        # « 148.750 » : 3 chiffres après le séparateur = milliers (les montants ont
        # 0 ou 2 décimales ; le FCFA n'en a pas)
        s = s.replace(".", "").replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return valeur


def normaliser(champs: dict, doc_type: dict) -> dict:
    """Tous les champs du type, dans l'ordre, nettoyés selon leur type."""
    resultat = {}
    for c in doc_type["champs"]:
        valeur = champs.get(c["nom"])
        if est_vide(valeur):
            valeur = None
        elif c["type"] == "date":
            valeur = normaliser_date(valeur)
        elif c["type"] == "montant":
            valeur = normaliser_montant(valeur)
        resultat[c["nom"]] = valeur
    return resultat


# --- Point d'entrée ---

def extraire(contenu: bytes, type_doc: str, approche: str | None = None) -> dict:
    """Extrait les champs d'un document dont l'utilisateur a choisi le type.

    approche : "vision" ou "ocr" (None = réglage APPROCHE du .env).
    """
    debut = time.perf_counter()
    approche = approche or settings.approche
    doc_type = charger_type(type_doc)  # erreur tout de suite si le type est inconnu
    doc = preparer_document(contenu, approche)

    rep = ollama.Client(host=settings.ollama_host).chat(
        model=settings.model_name,
        messages=[construire_message(doc, construire_prompt(doc_type))],
        format=construire_schema(doc_type),
        options={"temperature": 0, "num_ctx": settings.num_ctx},
        keep_alive=settings.keep_alive,
    )
    try:
        reponse = json.loads(rep["message"]["content"])
    except json.JSONDecodeError as e:
        raise ReponseModeleInvalide("Le modèle n'a pas renvoyé un JSON valide.") from e

    champs = evaluer(normaliser(reponse.get("champs") or {}, doc_type), doc_type, doc)
    alertes = []
    if doc.texte is None:
        alertes.append("Document lu en image par le modèle : la présence des valeurs dans le "
                       "document n'a pas pu être vérifiée automatiquement.")
    return {
        "version_format": VERSION_FORMAT,
        "type": doc_type["type"],
        "approche": approche,
        "source": doc.source,
        "modele": settings.model_name,
        "duree_s": round(time.perf_counter() - debut, 1),
        "champs": champs,
        "nb_a_verifier": sum(c["a_verifier"] for c in champs.values()),
        "alertes": alertes,
    }
