from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.services.image_upload import (
    IMAGE_MAX_SIDE,
    IMAGE_OPTIMIZE_THRESHOLD_BYTES,
    normalize_upload_image,
)


def test_normalize_upload_image_downscales_large_phone_photo() -> None:
    image = Image.effect_noise((3200, 2400), 100).convert("RGB")
    original = BytesIO()
    image.save(original, format="JPEG", quality=95)
    original_content = original.getvalue()
    upload_file = SimpleNamespace(filename="phone-photo.jpg", content_type="image/jpeg")

    assert len(original_content) > IMAGE_OPTIMIZE_THRESHOLD_BYTES

    content, content_type = normalize_upload_image(upload_file, original_content)

    assert content_type == "image/jpeg"
    assert len(content) < len(original_content)
    with Image.open(BytesIO(content)) as optimized:
        assert max(optimized.size) <= IMAGE_MAX_SIDE
