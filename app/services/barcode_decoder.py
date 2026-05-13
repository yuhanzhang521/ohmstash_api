from io import BytesIO
from typing import Iterable, List

import zxingcpp
from PIL import Image, ImageOps, UnidentifiedImageError


def decode_barcodes_from_image(content: bytes) -> List[str]:
    image = _load_image(content)
    raw_codes: List[str] = []
    seen_codes: set[str] = set()

    for variant in _build_decode_variants(image):
        for result in zxingcpp.read_barcodes(variant):
            text = str(result.text or "").strip()
            if text and text not in seen_codes:
                raw_codes.append(text)
                seen_codes.add(text)
        if raw_codes:
            break

    return raw_codes


def extract_box_codes(raw_codes: Iterable[str]) -> List[str]:
    box_codes: List[str] = []
    seen_codes: set[str] = set()
    for raw_code in raw_codes:
        normalized_code = _extract_box_code(raw_code)
        if normalized_code and normalized_code not in seen_codes:
            box_codes.append(normalized_code)
            seen_codes.add(normalized_code)
    return box_codes


def _load_image(content: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(content))
        return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Unsupported image file") from exc


def _build_decode_variants(image: Image.Image) -> List[Image.Image]:
    variants = [image]
    grayscale = ImageOps.grayscale(image)
    variants.append(grayscale)
    variants.append(ImageOps.autocontrast(grayscale))

    for threshold in (96, 128, 160):
        variants.append(grayscale.point(lambda value: 255 if value > threshold else 0))

    width, height = image.size
    crop_size = int(min(width, height) * 0.72)
    if crop_size > 0 and (width != crop_size or height != crop_size):
        left = max((width - crop_size) // 2, 0)
        top = max((height - crop_size) // 2, 0)
        crop = image.crop((left, top, left + crop_size, top + crop_size))
        crop_grayscale = ImageOps.grayscale(crop)
        variants.extend(
            [
                crop,
                crop_grayscale,
                ImageOps.autocontrast(crop_grayscale),
            ]
        )

    return variants


def _extract_box_code(raw_code: str) -> str:
    text = raw_code.strip()
    if not text:
        return ""
    upper_text = text.upper()
    marker = "BOX-"
    index = upper_text.find(marker)
    if index < 0:
        return ""

    code_chars: List[str] = []
    for char in text[index:]:
        if char.isalnum() or char in {"-", "_"}:
            code_chars.append(char)
        else:
            break
    return "".join(code_chars).upper()
