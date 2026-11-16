import pytest
from fastapi.testclient import TestClient

from api.core import extraction
from api.core.extraction import (charger_type, construire_message, construire_prompt,
                                 construire_schema, lister_types, normaliser, normaliser_date,
                                 normaliser_montant)
from api.core.fichiers import Document
from api.main import app


# --- Types de documents ---

def test_tous_les_types_sont_valides():
    for t in lister_types():
        assert t["description"] and t["champs"]
        for c in t["champs"]:
            assert c["type"] in extraction.TYPES_JSON, f"{t['type']}.{c['nom']}"
            assert c["description"], f"{t['type']}.{c['nom']} sans description"


@pytest.mark.parametrize("nom", ["passeport_martien", "../config", "Facture"])
def test_type_inconnu(nom):
    with pytest.raises(ValueError):
        charger_type(nom)


# --- Ce qu'on envoie au modèle ---

def test_prompt_contient_les_champs_et_descriptions():
    t = charger_type("facture")
    prompt = construire_prompt(t)
    for champ in t["champs"]:
        assert champ["nom"] in prompt and champ["description"] in prompt
    # sans cette consigne, le modèle 7b réécrit parfois les valeurs en « minuscules_avec_tirets »
    assert "mêmes majuscules" in prompt


def test_schema_impose_tous_les_champs():
    t = charger_type("facture")
    champs = construire_schema(t)["properties"]["champs"]
    assert champs["required"] == [c["nom"] for c in t["champs"]]
    assert champs["properties"]["montant_ttc"]["type"] == ["number", "string", "null"]
    assert champs["properties"]["fournisseur"]["type"] == ["string", "null"]


def test_message_texte_ou_images():
    msg = construire_message(Document(texte="Total TTC : 10 EUR"), "CONSIGNE")
    assert msg["content"].index("Total TTC") < msg["content"].index("CONSIGNE")
    assert "images" not in msg
    assert construire_message(Document(images=[b"a"]), "CONSIGNE")["images"] == [b"a"]


# --- Nettoyage des valeurs ---

@pytest.mark.parametrize("entree,attendu", [
    ("2026-10-03", "2026-10-03"), ("03/10/2026", "2026-10-03"), ("3.1.2026", "2026-01-03"),
    ("octobre 2026", "octobre 2026"), (None, None),
])
def test_normaliser_date(entree, attendu):
    assert normaliser_date(entree) == attendu


@pytest.mark.parametrize("entree,attendu", [
    (491.72, 491.72), (300, 300.0), ("491,72 €", 491.72), ("1 234,56 EUR", 1234.56),
    ("1.234,56", 1234.56), ("1,234.56", 1234.56), ("illisible", "illisible"), (None, None),
    # montants en FCFA (points ou espaces pour les milliers, pas de décimales)
    ("148.750 FCFA", 148750.0), ("1.487.500 FCFA", 1487500.0), ("125 000 FCFA", 125000.0),
    ("23 750", 23750.0), ("16,50", 16.5), ("0,900", 0.9),
])
def test_normaliser_montant(entree, attendu):
    assert normaliser_montant(entree) == attendu


def test_normaliser_complete_et_ordonne_les_champs():
    t = charger_type("facture")
    resultat = normaliser({"montant_ttc": "10,50 €", "tva": "null", "champ_invente": "x"}, t)
    assert list(resultat) == [c["nom"] for c in t["champs"]]
    assert resultat["montant_ttc"] == 10.5
    assert resultat["tva"] is None  # « null » écrit en texte par le modèle
    assert resultat["fournisseur"] is None


# --- API, avec un faux modèle ---

class FauxClient:
    """Remplace Ollama : renvoie une réponse préparée et garde les appels."""
    def __init__(self, reponse):
        self.reponse, self.appels = reponse, []

    def chat(self, **kwargs):
        self.appels.append(kwargs)
        return {"message": {"content": self.reponse}}


@pytest.fixture
def faux_modele(monkeypatch):
    def installer(reponse, document):
        client = FauxClient(reponse)
        client.approches = []
        monkeypatch.setattr(extraction.ollama, "Client", lambda host: client)

        def faux_preparer(contenu, approche):
            client.approches.append(approche)
            return document
        monkeypatch.setattr(extraction, "preparer_document", faux_preparer)
        return client
    return installer


FACTURE_TEXTE = ("SARL Boulangerie Dupont\nFACTURE N° FA-2026-0142\nDate : 03/10/2026\n"
                 "Total HT\t300,00 EUR\nTVA 5,5 %\t16,50 EUR\nTotal TTC\t316,50 EUR")


def test_api_extraction(faux_modele):
    client = faux_modele(
        '{"champs": {"fournisseur": "SARL Boulangerie Dupont", "client": null, "date": "2026-10-03",'
        ' "numero_facture": "FA-2026-0142", "montant_ht": "300,00", "tva": 16.5, "montant_ttc": 316.5}}',
        Document(texte=FACTURE_TEXTE, source="image_ocr"),
    )
    r = TestClient(app).post("/extract/facture", files={"fichier": ("f.jpg", b"x")})
    assert r.status_code == 200
    j = r.json()
    assert j["version_format"] == 1
    assert j["type"] == "facture" and j["approche"] == "ocr" and j["source"] == "image_ocr"
    assert isinstance(j["duree_s"], float)
    assert j["champs"]["montant_ht"] == {"valeur": 300.0, "a_verifier": False, "raisons": []}
    assert j["champs"]["client"] == {"valeur": None, "a_verifier": True,
                                     "raisons": ["absent du document ou illisible"]}
    assert j["nb_a_verifier"] == 1
    assert j["alertes"] == []
    assert len(client.appels) == 1


def test_api_choix_de_lapproche(faux_modele):
    client = faux_modele('{"champs": {}}', Document(images=[b"jpeg"], source="image_vision"))
    j = TestClient(app).post("/extract/facture?approche=vision", files={"fichier": ("f.jpg", b"x")}).json()
    assert client.approches == ["vision"]
    assert j["approche"] == "vision"
    assert j["alertes"]  # en vision, la présence des valeurs n'est pas vérifiable


def test_api_reponse_du_modele_invalide(faux_modele):
    faux_modele("pas du json", Document(texte="x", source="pdf_texte"))
    r = TestClient(app).post("/extract/facture", files={"fichier": ("f.pdf", b"x")})
    assert r.status_code == 502


def test_api_erreurs():
    client = TestClient(app)
    assert client.post("/extract/passeport_martien", files={"fichier": ("f.pdf", b"%PDF")}).status_code == 404
    assert client.post("/extract/facture?approche=magie", files={"fichier": ("f.jpg", b"x")}).status_code == 422
    assert client.post("/extract/facture", files={"fichier": ("f.zip", b"PK\x03\x04")}).status_code == 415


def test_api_fichier_trop_gros(monkeypatch):
    monkeypatch.setattr(extraction.settings, "taille_max_mo", 1)
    r = TestClient(app).post("/extract/facture", files={"fichier": ("f.jpg", b"x" * (1024 * 1024 + 1))})
    assert r.status_code == 413


def test_api_liste_des_types():
    types = TestClient(app).get("/types").json()
    assert {t["type"] for t in types} == {"facture", "avis_echeance"}
    assert all("description" in c for t in types for c in t["champs"])
