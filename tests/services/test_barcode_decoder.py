from pathlib import Path

from app.services import barcode_decoder


def test_decode_data_matrix_from_phone_photo() -> None:
    image_path = Path("tests/dm_test.jpg")
    raw_codes = barcode_decoder.decode_barcodes_from_image(image_path.read_bytes())

    assert raw_codes == ["DataMatrix Content Is Here!"]


def test_extract_box_codes_from_label_payloads() -> None:
    assert barcode_decoder.extract_box_codes(
        ["https://example.test/box/BOX-0148", "BOX-test_02 extra"],
    ) == ["BOX-0148", "BOX-TEST_02"]
