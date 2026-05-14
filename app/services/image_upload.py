from io import BytesIO
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

IMAGE_OPTIMIZE_THRESHOLD_BYTES = 3 * 1024 * 1024
IMAGE_TARGET_MAX_BYTES = 3 * 1024 * 1024
IMAGE_MAX_SIDE = 2400
JPEG_QUALITY_STEPS = (88, 82, 76, 70)

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
        return _optimize_standard_image(content, inferred_type)

    return _optimize_standard_image(content, content_type)


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


def _optimize_standard_image(content: bytes, content_type: str) -> Tuple[bytes, str]:
    if len(content) <= IMAGE_OPTIMIZE_THRESHOLD_BYTES:
        return content, content_type
    if content_type == "image/gif":
        return content, content_type

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ValueError(
            "Image optimization requires Pillow. Please install project requirements."
        ) from exc

    try:
        with Image.open(BytesIO(content)) as image:
            normalized_image = ImageOps.exif_transpose(image)
            resample_filter = getattr(Image, "Resampling", Image).LANCZOS
            normalized_image.thumbnail(
                (IMAGE_MAX_SIDE, IMAGE_MAX_SIDE),
                resample_filter,
            )
            rgb_image = _convert_image_to_rgb(normalized_image)
            best_content = content
            for quality in JPEG_QUALITY_STEPS:
                output = BytesIO()
                rgb_image.save(
                    output,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )
                optimized_content = output.getvalue()
                if len(optimized_content) <= IMAGE_TARGET_MAX_BYTES:
                    return optimized_content, "image/jpeg"
                if len(optimized_content) < len(best_content):
                    best_content = optimized_content
            if best_content is not content:
                return best_content, "image/jpeg"
    except Exception:
        return content, content_type

    return content, content_type


def _convert_image_to_rgb(image: "Image.Image") -> "Image.Image":
    from PIL import Image

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba_image = image.convert("RGBA")
        background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
        background.alpha_composite(rgba_image)
        return background.convert("RGB")
    return image.convert("RGB")
