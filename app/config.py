import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'taman.db').as_posix()}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 5 * 1024 * 1024
LISTINGS_PER_PAGE = 12
SESSION_MAX_AGE = 14 * 24 * 3600
# Mettre HTTPS_ONLY=1 en production (cookie de session envoyé uniquement en HTTPS)
HTTPS_ONLY = os.getenv("HTTPS_ONLY", "0") == "1"


def _load_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    # En dev : clé générée une fois et conservée pour que les sessions survivent aux redémarrages
    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    return key


SECRET_KEY = _load_secret_key()
