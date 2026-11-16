# Contrat API

Base URL locale : `http://localhost:8000`.

## `GET /health`

Retourne `200 OK` si l'API est disponible :

```json
{"status": "ok"}
```

## `GET /document-types`

Retourne la liste des types chargés depuis les fichiers YAML :

```json
{
  "document_types": [
    {
      "name": "invoice",
      "fields": [
        {"name": "fournisseur", "type": "string", "description": "Nom du fournisseur"}
      ]
    }
  ]
}
```

## `POST /extract`

La requête est `multipart/form-data` :

| Champ | Type | Obligatoire | Description |
| --- | --- | --- | --- |
| `file` | fichier image | oui | Image du document à lire |
| `document_type` | chaîne | oui | Identifiant configuré, par exemple `invoice` |
| `model` | chaîne | oui | `qwen_vl` ou `paddleocr_vl` |

Exemple de réponse `200 OK` :

```json
{
  "document_type": "invoice",
  "model": "qwen_vl",
  "fields": {
    "fournisseur": {"value": "ACME SARL", "confidence": 0.93},
    "date": {"value": "2026-11-10", "confidence": 0.88}
  },
  "low_confidence_fields": ["tva"]
}
```

La confiance est un nombre compris entre `0` et `1`. Un champ est douteux si sa confiance est strictement inférieure à `LOW_CONFIDENCE_THRESHOLD` (défaut `0.7`). Les extracteurs actuels sont factices : leurs valeurs ne doivent pas être considérées comme des résultats de reconnaissance.

Les erreurs de requête suivent le format d'erreur HTTP standard de FastAPI (par exemple `422` pour une entrée invalide et `404` pour un type de document inconnu).
