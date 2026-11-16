import pytest

from api.core.controles import (RAISON_DATE, RAISON_INTROUVABLE, RAISON_MONTANT, RAISON_OCR,
                                RAISON_VIDE, evaluer, valeur_dans_texte)
from api.core.extraction import charger_type
from api.core.fichiers import Document

FACTURE = charger_type("facture")
TEXTE = ("SARL Boulangerie Dupont\nFACTURE N° FA-2026-0142\nDate d'émission : 3 octobre 2026\n"
         "Total HT\t1 300,00 EUR\nTVA 20 %\t260,00 EUR\nTotal TTC\t1 560,00 EUR")
BONS_CHAMPS = {"fournisseur": "SARL Boulangerie Dupont", "client": None, "date": "2026-10-03",
               "numero_facture": "FA-2026-0142", "montant_ht": 1300.0, "tva": 260.0,
               "montant_ttc": 1560.0}


def _raisons(resultat):
    return {nom: c["raisons"] for nom, c in resultat.items() if c["a_verifier"]}


@pytest.mark.parametrize("valeur,type_champ,texte,attendu", [
    (1300.0, "montant", "Total HT 1 300,00 EUR", True),
    (1300.0, "montant", "Total HT 1.300,00", True),
    (316.5, "montant", "Total 316.50", True),
    (316.5, "montant", "Total 31650", False),
    ("2026-10-03", "date", "le 03/10/2026", True),
    ("2026-10-03", "date", "le 3 octobre 2026", True),
    ("2026-10-03", "date", "le 1er octobre 2026", False),
    ("Café du Centre", "texte", "Client : CAFE  DU CENTRE", True),
    ("Café du Nord", "texte", "Client : Café du Centre", False),
])
def test_valeur_dans_texte(valeur, type_champ, texte, attendu):
    assert valeur_dans_texte(valeur, type_champ, texte) is attendu


def test_champs_corrects_seul_le_vide_est_signale():
    resultat = evaluer(BONS_CHAMPS, FACTURE, Document(texte=TEXTE))
    assert _raisons(resultat) == {"client": [RAISON_VIDE]}
    assert resultat["montant_ttc"] == {"valeur": 1560.0, "a_verifier": False, "raisons": []}


def test_valeur_inventee_signalee():
    champs = {**BONS_CHAMPS, "numero_facture": "FA-2026-9999"}
    assert _raisons(evaluer(champs, FACTURE, Document(texte=TEXTE)))["numero_facture"] == [RAISON_INTROUVABLE]


def test_formats_non_reconnus():
    champs = {**BONS_CHAMPS, "date": "octobre 2026", "montant_ht": "illisible"}
    r = _raisons(evaluer(champs, FACTURE, Document(texte=TEXTE)))
    assert r["date"] == [RAISON_DATE]
    assert RAISON_MONTANT in r["montant_ht"]


def test_ht_plus_tva_different_du_ttc():
    texte = TEXTE.replace("1 560,00", "1 650,00")
    champs = {**BONS_CHAMPS, "montant_ttc": 1650.0}
    r = _raisons(evaluer(champs, FACTURE, Document(texte=texte)))
    for nom in ("montant_ht", "tva", "montant_ttc"):
        assert r[nom] == ["montant_ht + tva ≠ montant_ttc"]


def test_lecture_ocr_incertaine():
    blocs = [("FACTURE N° FA-2026-0142", 0.98), ("1 560,00 EUR", 0.62)]
    r = _raisons(evaluer(BONS_CHAMPS, FACTURE, Document(texte=TEXTE, blocs_ocr=blocs)))
    assert r["montant_ttc"] == [RAISON_OCR]
    assert "numero_facture" not in r


def test_facture_fcfa_ttc_mal_lu_signale():
    # l'OCR lit 1.487.500 au lieu de 148.750 pour le TTC : l'incohérence doit être signalée
    texte = "SAHEL BUREAUTIQUE SARL\nTotal HT 125.000 FCFA\nTVA 23.750 FCFA\nTotal TTC 1.487.500 FCFA"
    champs = {"fournisseur": "SAHEL BUREAUTIQUE SARL", "client": None, "date": None,
              "numero_facture": None, "montant_ht": 125000.0, "tva": 23750.0, "montant_ttc": 1487500.0}
    r = _raisons(evaluer(champs, FACTURE, Document(texte=texte)))
    assert r["montant_ttc"] == ["montant_ht + tva ≠ montant_ttc"]
    assert r["montant_ht"] == ["montant_ht + tva ≠ montant_ttc"]


def test_document_lu_en_image_pas_de_controle_de_presence():
    champs = {**BONS_CHAMPS, "numero_facture": "FA-2026-9999"}
    r = _raisons(evaluer(champs, FACTURE, Document(images=[b"jpeg"])))
    assert r == {"client": [RAISON_VIDE]}
