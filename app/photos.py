from uuid import uuid4

from starlette.datastructures import FormData, UploadFile

from .config import MAX_PHOTO_BYTES, UPLOAD_DIR


def _detect_extension(head: bytes) -> str | None:
    # On se fie au contenu réel du fichier, pas à son nom ni au Content-Type envoyé
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def uploaded_photos(form: FormData) -> list[UploadFile]:
    # Un champ fichier laissé vide est envoyé avec un nom de fichier vide
    return [f for f in form.getlist("photos") if isinstance(f, UploadFile) and f.filename]


async def save_photo(upload: UploadFile) -> str:
    data = await upload.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError(f"« {upload.filename} » dépasse {MAX_PHOTO_BYTES // (1024 * 1024)} Mo.")
    ext = _detect_extension(data[:12])
    if ext is None:
        raise ValueError(f"« {upload.filename} » n'est pas une image JPEG, PNG ou WebP.")
    filename = f"{uuid4().hex}.{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / filename).write_bytes(data)
    return filename


def delete_photo_file(filename: str) -> None:
    (UPLOAD_DIR / filename).unlink(missing_ok=True)
