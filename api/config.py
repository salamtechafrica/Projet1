from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Modèle (servi par Ollama) ---
    # Le plan prévoit Qwen-VL 7b (GPU / Colab). Sur un PC sans carte graphique : qwen2.5vl:3b.
    model_name: str = "qwen2.5vl:3b"
    ollama_host: str = "http://localhost:11434"
    # Durée pendant laquelle Ollama garde le modèle en mémoire après un appel.
    keep_alive: str = "30m"
    # Mémoire de travail du modèle, en tokens (une page en 1280 px en utilise ~1600).
    num_ctx: int = 8192

    # --- Les deux approches à comparer (note de projet, §5) ---
    # "vision" : Qwen-VL lit directement l'image et renvoie les champs (une étape).
    # "ocr"    : un OCR lit le texte, puis Qwen range les informations dans les champs.
    approche: Literal["vision", "ocr"] = "ocr"
    # Moteur OCR de l'approche "ocr" :
    # "rapidocr"     : léger, tourne partout (même sans GPU), ~3 s par page sur CPU ;
    # "paddleocr_vl" : celui du plan ; Python 3.8-3.12 et GPU conseillé (Colab).
    ocr_moteur: Literal["rapidocr", "paddleocr_vl"] = "rapidocr"
    # Confiance moyenne minimale de l'OCR (0 à 1) ; en dessous, on bascule sur la vision.
    ocr_score_min: float = 0.75

    # --- Préparation des fichiers ---
    # Taille maximale d'un fichier envoyé, en Mo.
    taille_max_mo: int = 20
    # Plus grand côté de l'image envoyée au modèle, en pixels.
    image_max_px: int = 1280
    # Nombre maximum de pages lues dans un PDF.
    pdf_max_pages: int = 3

    # --- Signalement des champs douteux ---
    # Un champ lu par l'OCR avec une confiance plus faible que ce seuil est à vérifier.
    seuil_doute_ocr: float = 0.9

    class Config:
        env_file = ".env"
        extra = "ignore"  # un ancien réglage resté dans le .env ne bloque pas le démarrage


settings = Settings()
