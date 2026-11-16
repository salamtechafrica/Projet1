"""Interface Streamlit pour l'extraction et la vérification de documents."""

import os
from typing import Any

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
MODEL_OPTIONS = {
    "Qwen-VL": "qwen_vl",
    "PaddleOCR-VL": "paddleocr_vl",
}


def request_document_types() -> list[dict[str, Any]]:
    """Récupère les types configurés dans l'API."""
    response = requests.get(f"{API_URL}/document-types", timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload["document_types"]


def extract_document(image: Any, document_type: str, model: str) -> dict[str, Any]:
    """Envoie l'image et les paramètres sélectionnés à l'API."""
    response = requests.post(
        f"{API_URL}/extract",
        files={"file": (image.name, image.getvalue(), image.type or "application/octet-stream")},
        data={"document_type": document_type, "model": model},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    """Construit l'écran d'import, de préremplissage et de validation."""
    st.set_page_config(page_title="Lecture de documents", page_icon="📄")
    st.title("Outil de lecture automatique de documents")
    st.caption("Importez une image, choisissez un modèle puis vérifiez les champs extraits.")

    try:
        document_types = request_document_types()
    except requests.RequestException as exc:
        st.error(f"Impossible de joindre l'API ({API_URL}) : {exc}")
        return

    if not document_types:
        st.error("Aucun type de document n'est configuré dans l'API.")
        return

    type_names = [item["name"] for item in document_types]
    selected_type = st.selectbox("Type de document", type_names)
    selected_model_label = st.selectbox("Modèle", list(MODEL_OPTIONS))
    image = st.file_uploader("Photo du document", type=["png", "jpg", "jpeg", "webp"])

    if st.button("Lire le document", type="primary", disabled=image is None):
        try:
            st.session_state["extraction"] = extract_document(
                image=image,
                document_type=selected_type,
                model=MODEL_OPTIONS[selected_model_label],
            )
        except requests.RequestException as exc:
            st.error(f"L'extraction a échoué : {exc}")
            return

    extraction = st.session_state.get("extraction")
    if not extraction or extraction.get("document_type") != selected_type:
        return

    st.subheader("Vérification")
    doubtful_fields = set(extraction["low_confidence_fields"])
    updated_fields: dict[str, str] = {}
    with st.form("verification_form"):
        for field_name, result in extraction["fields"].items():
            confidence = result["confidence"]
            if field_name in doubtful_fields:
                st.markdown(f":orange[À vérifier — {field_name} ({confidence:.0%})]")
            else:
                st.caption(f"{field_name} — confiance {confidence:.0%}")
            updated_fields[field_name] = st.text_input(
                field_name,
                value="" if result["value"] is None else str(result["value"]),
                key=f"field_{field_name}",
            )
        validated = st.form_submit_button("Valider")

    if validated:
        # TODO(integration): enregistrer les valeurs validées dans storage/ et proposer un export.
        st.success("Document validé. L'enregistrement et l'export seront intégrés ultérieurement.")


if __name__ == "__main__":
    main()
