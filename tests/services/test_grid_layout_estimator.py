from pathlib import Path

from app.services.grid_layout_estimator import estimate_grid_layout


TEST_DATA_DIR = Path(__file__).resolve().parents[1]


def test_estimate_grid_layout_counts_flat_3x13_grid() -> None:
    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"

    estimate = estimate_grid_layout(image_path.read_bytes())

    assert estimate is not None
    assert estimate.rows == 13
    assert estimate.cols == 3
    assert estimate.horizontal_lines == 14
    assert estimate.vertical_lines == 4
