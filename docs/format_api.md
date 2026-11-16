# Format d'échange de l'API — version 1

Ce document fixe ce que l'API reçoit et renvoie. L'interface (Streamlit) et le script
d'évaluation peuvent s'appuyer dessus dès maintenant, même sans modèle installé.

**Règle :** tout changement de ce format passe par une pull request qui modifie aussi
ce fichier et augmente `version_format`.

Adresse par défaut : `http://localhost:8000` · Documentation interactive : `/docs`

---

## 1. Liste des types de documents

`GET /types`

Sert à remplir la liste de choix « type de document » de l'interface.

```json
[
  {
    "type": "facture",
    "description": "Facture d'un fournisseur ou prestataire…",
    "champs": [
      {"nom": "fournisseur", "type": "texte", "description": "nom de l'entreprise qui émet la facture"},
      {"nom": "date", "type": "date", "description": "date d'émission de la facture"},
      {"nom": "montant_ttc", "type": "montant", "description": "total toutes taxes comprises…"}
    ]
  }
]
```

Types de champ possibles : `texte`, `date`, `montant`.

---

## 2. Extraire un document

`POST /extract/{type}` — l'utilisateur a choisi le type (ex. `/extract/facture`).

| Paramètre | Où | Obligatoire | Valeurs |
| --- | --- | --- | --- |
| `fichier` | formulaire (multipart) | oui | image (JPEG, PNG, WebP, HEIC, TIFF…) ou PDF |
| `approche` | URL (`?approche=`) | non | `vision` ou `ocr` ; vide = réglage du serveur |

Les deux approches sont celles que le plan demande de comparer :
- `vision` : Qwen-VL lit directement l'image et remplit les champs ;
- `ocr` : un OCR lit le texte, puis Qwen range les informations dans les champs.

Exemple :
```powershell
curl.exe -F "fichier=@facture.jpg" "http://localhost:8000/extract/facture?approche=ocr"
```

### Réponse (200)

```json
{
  "version_format": 1,
  "type": "facture",
  "approche": "ocr",
  "source": "image_ocr",
  "modele": "qwen2.5vl:7b",
  "duree_s": 4.2,
  "champs": {
    "fournisseur":    {"valeur": "SARL Boulangerie Dupont", "a_verifier": false, "raisons": []},
    "client":         {"valeur": null, "a_verifier": true, "raisons": ["absent du document ou illisible"]},
    "date":           {"valeur": "2026-10-03", "a_verifier": false, "raisons": []},
    "numero_facture": {"valeur": "FA-2026-0142", "a_verifier": false, "raisons": []},
    "montant_ht":     {"valeur": 300.0, "a_verifier": true, "raisons": ["montant_ht + tva ≠ montant_ttc"]},
    "tva":            {"valeur": 16.5, "a_verifier": true, "raisons": ["montant_ht + tva ≠ montant_ttc"]},
    "montant_ttc":    {"valeur": 361.5, "a_verifier": true, "raisons": ["montant_ht + tva ≠ montant_ttc"]}
  },
  "nb_a_verifier": 4,
  "alertes": []
}
```

| Clé | Sens |
| --- | --- |
| `champs` | **Toujours tous les champs du type, dans l'ordre de `/types`**, même vides. |
| `champs.*.valeur` | `texte` → chaîne ; `date` → `"AAAA-MM-JJ"` ; `montant` → nombre (`316.5`) ; `null` si absent. Une date ou un montant non reconnu reste une chaîne et est marqué à vérifier. |
| `champs.*.a_verifier` | `true` = **afficher le champ en couleur** pour que la personne le contrôle. |
| `champs.*.raisons` | Pourquoi le champ est douteux (à afficher en info-bulle). Voir § 3. |
| `nb_a_verifier` | Nombre de champs à vérifier (pratique pour un résumé ou un tri). |
| `alertes` | Messages qui concernent tout le document (ex. lu en image, contrôles limités). |
| `approche` | Approche réellement utilisée : `vision` ou `ocr`. |
| `source` | Comment le contenu a été obtenu : `pdf_texte` (texte exact du PDF), `image_ocr`, `pdf_scanne_ocr`, `image_vision`, `pdf_scanne_vision`. En approche `ocr`, `*_vision` signifie que l'OCR a échoué et que la vision a pris le relais. |
| `modele` | Modèle utilisé (utile pour comparer dans l'évaluation). |
| `duree_s` | Temps de traitement côté serveur, en secondes. |

---

## 3. Raisons de doute possibles

| Raison | Signification |
| --- | --- |
| `absent du document ou illisible` | Le modèle n'a rien trouvé (`valeur` = `null`). |
| `date non reconnue` | La date n'a pas pu être mise au format AAAA-MM-JJ. |
| `montant non reconnu` | Le montant n'a pas pu être converti en nombre. |
| `valeur introuvable dans le texte du document` | La valeur n'apparaît pas dans le texte lu : le modèle a pu l'inventer ou la déformer. Contrôle possible seulement quand le document a été lu en texte (`pdf_texte`, `*_ocr`). |
| `lecture OCR incertaine` | L'OCR a lu ce passage avec une faible confiance (moteur `rapidocr` uniquement). |
| `montant_ht + tva ≠ montant_ttc` | Incohérence de calcul : les champs concernés sont tous signalés. |

---

## 4. Erreurs

Le corps d'une erreur est `{"detail": "message lisible"}`.

| Code | Cas |
| --- | --- |
| 404 | Type de document inconnu. |
| 413 | Fichier trop gros (20 Mo maximum par défaut, réglage `TAILLE_MAX_MO`). |
| 415 | Fichier qui n'est ni une image ni un PDF lisible (ou PDF protégé / abîmé). |
| 422 | Paramètre invalide (ex. `approche` autre que `vision` / `ocr`, fichier manquant). |
| 502 | Le modèle a renvoyé une réponse inexploitable (réessayer). |
| 503 | Moteur OCR demandé non installé sur le serveur (ex. PaddleOCR-VL). |
| 500 | Autre problème serveur, le plus souvent Ollama arrêté ou modèle non téléchargé. |

---

## 5. Pour l'évaluation

Pour comparer les deux approches sur les mêmes documents, appeler pour chaque document :
`/extract/facture?approche=vision` puis `/extract/facture?approche=ocr`, et comparer
`champs.*.valeur` aux bonnes réponses. Comparer les montants comme des nombres et les dates
au format AAAA-MM-JJ. `duree_s` et `modele` permettent d'ajouter la vitesse au tableau.
