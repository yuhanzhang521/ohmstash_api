from io import BytesIO
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

ALLOWED_IMAGE_EXTENSIONS = {
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
}


def normalize_upload_image(file: UploadFile, content: bytes) -> Tuple[bytes, str]:
    if not content:
        raise ValueError("Uploaded image is empty")

    extension = Path(file.filename or "").suffix.lower()
    content_type = file.content_type or ""
    is_known_image = content_type.startswith("image/") or extension in ALLOWED_IMAGE_EXTENSIONS
    if not is_known_image:
        raise ValueError("Uploaded file must be an image")

    if extension in {".heic", ".heif"} or content_type in {"image/heic", "image/heif"}:
        return _convert_heic_to_jpeg(content)

    if not content_type or content_type == "application/octet-stream":
        inferred_type = _infer_content_type(extension)
        return content, inferred_type

    return content, content_type


def _infer_content_type(extension: str) -> str:
    if extension == ".png":
        return "image/png"
    if extension == ".webp":
        return "image/webp"
    if extension == ".gif":
        return "image/gif"
    if extension in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if extension in {".heic", ".heif"}:
        return "image/heic"
    return "application/octet-stream"


def _convert_heic_to_jpeg(content: bytes) -> Tuple[bytes, str]:
    try:
        from PIL import Image
        from pillow_heif import register_heif_opener
    except ImportError as exc:
        raise ValueError(
            "HEIC support requires Pillow and pillow-heif. Please install project requirements."
        ) from exc

    register_heif_opener()
    try:
        with Image.open(BytesIO(content)) as image:
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=92)
            return output.getvalue(), "image/jpeg"
    except Exception as exc:
        raise ValueError("HEIC image could not be converted to JPEG") from exc
