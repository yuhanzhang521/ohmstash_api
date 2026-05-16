from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps


MIN_BAND_COUNT = 2
MAX_BAND_COUNT = 30
PROJECTION_STEP_TARGET = 600
PROJECTION_MARGIN_RATIO = 0.05
EDGE_DARK_THRESHOLD = 80
BORDER_MARGIN_RATIO = 0.08
BOUNDARY_TOLERANCE_RATIO = 0.32
MIN_CONFIDENCE = 0.0
CLOSE_SCORE_RATIO = 0.80
MAX_DENSE_BAND_COUNT = 13
ASPECT_RATIO_FLAT_GRID_THRESHOLD = 1.2
FLAT_GRID_MAX_SHORT_BAND_COUNT = 6


@dataclass(frozen=True)
class GridLayoutEstimate:
    rows: int
    cols: int
    horizontal_lines: int
    vertical_lines: int


def estimate_grid_layout(content: bytes) -> GridLayoutEstimate | None:
    try:
        with Image.open(BytesIO(content)) as image:
            grayscale_image = ImageOps.exif_transpose(image).convert("L")
            return _estimate_grid_layout_from_image(grayscale_image)
    except Exception:
        return None


def build_grid_layout_hint(estimate: GridLayoutEstimate | None) -> str:
    if estimate is None:
        return ""
    return (
        "\n本地图像分析提示：规则网格分隔线检测估算 "
        f"rows={estimate.rows}, cols={estimate.cols}, "
        f"horizontal_lines={estimate.horizontal_lines}, vertical_lines={estimate.vertical_lines}。"
        "如果视觉判断没有更强证据，请优先采用这个 rows/cols。"
    )


def _estimate_grid_layout_from_image(image: "Image.Image") -> GridLayoutEstimate | None:
    width, height = image.size
    line_image = image.filter(ImageFilter.FIND_EDGES)
    horizontal_scores = _projection_scores(
        image=line_image,
        axis="horizontal",
        length=height,
        cross_length=width,
    )
    vertical_scores = _projection_scores(
        image=line_image,
        axis="vertical",
        length=width,
        cross_length=height,
    )
    row_fit = _fit_regular_grid(horizontal_scores)
    col_fit = _fit_regular_grid(
        vertical_scores,
        max_dense_band_count=(
            FLAT_GRID_MAX_SHORT_BAND_COUNT
            if height / width >= ASPECT_RATIO_FLAT_GRID_THRESHOLD
            else MAX_DENSE_BAND_COUNT
        ),
        min_band_count=3 if height / width >= ASPECT_RATIO_FLAT_GRID_THRESHOLD else MIN_BAND_COUNT,
        prefer_dense=height / width < ASPECT_RATIO_FLAT_GRID_THRESHOLD,
    )
    if row_fit is None or col_fit is None:
        return None
    return GridLayoutEstimate(
        rows=row_fit[0],
        cols=col_fit[0],
        horizontal_lines=row_fit[0] + 1,
        vertical_lines=col_fit[0] + 1,
    )


def _projection_scores(
    *,
    image: "Image.Image",
    axis: str,
    length: int,
    cross_length: int,
) -> list[float]:
    start = round(cross_length * PROJECTION_MARGIN_RATIO)
    end = round(cross_length * (1 - PROJECTION_MARGIN_RATIO))
    step = max(1, cross_length // PROJECTION_STEP_TARGET)
    scores: list[float] = []
    for index in range(length):
        total = 0
        edge_total = 0
        for sample in range(start, end, step):
            value = image.getpixel((sample, index)) if axis == "horizontal" else image.getpixel((index, sample))
            total += 1
            if value >= EDGE_DARK_THRESHOLD:
                edge_total += 1
        scores.append(edge_total / total if total else 0)
    return scores


def _fit_regular_grid(
    scores: list[float],
    *,
    max_dense_band_count: int = MAX_DENSE_BAND_COUNT,
    min_band_count: int = MIN_BAND_COUNT,
    prefer_dense: bool = True,
) -> tuple[int, float] | None:
    length = len(scores)
    if length <= 0:
        return None
    smoothed_scores = _smooth_scores(scores)
    candidates: list[tuple[int, float]] = []
    for band_count in range(min_band_count, min(MAX_BAND_COUNT, length // 8) + 1):
        score = _grid_fit_score(smoothed_scores, band_count)
        if score > 0:
            candidates.append((band_count, score))
    if not candidates:
        return None
    if not prefer_dense:
        return max(candidates, key=lambda candidate: candidate[1])
    best_score = max(score for _, score in candidates)
    close_candidates = [
        candidate
        for candidate in candidates
        if candidate[1] >= best_score * CLOSE_SCORE_RATIO
    ]
    dense_candidates = [
        candidate
        for candidate in close_candidates
        if candidate[0] <= max_dense_band_count
    ]
    selected = max(dense_candidates or close_candidates, key=lambda candidate: candidate[0])
    return selected


def _smooth_scores(scores: list[float]) -> list[float]:
    smoothed: list[float] = []
    for index in range(len(scores)):
        start = max(0, index - 2)
        end = min(len(scores), index + 3)
        smoothed.append(max(scores[start:end]))
    return smoothed


def _grid_fit_score(scores: list[float], band_count: int) -> float:
    length = len(scores)
    start_min = round(length * BORDER_MARGIN_RATIO)
    start_max = round(length * (1 - BORDER_MARGIN_RATIO))
    best_score = 0.0
    for start in _candidate_boundaries(scores, start_min, start_max):
        for end in _candidate_boundaries(scores, start + band_count * 4, start_max):
            spacing = (end - start) / band_count
            if spacing <= 0:
                continue
            tolerance = max(2, round(spacing * BOUNDARY_TOLERANCE_RATIO))
            if start - tolerance < 0 or end + tolerance >= length:
                continue
            boundary_scores = []
            for boundary_index in range(band_count + 1):
                center = round(start + spacing * boundary_index)
                boundary_scores.append(_local_max(scores, center, tolerance))
            score = sum(boundary_scores) / len(boundary_scores)
            score *= min(1.0, spacing / 20)
            if score > best_score:
                best_score = score
    return best_score


def _candidate_boundaries(scores: list[float], start: int, end: int) -> list[int]:
    bounded_start = max(0, start)
    bounded_end = min(len(scores) - 1, end)
    if bounded_end < bounded_start:
        return []
    candidates = sorted(
        range(bounded_start, bounded_end + 1),
        key=lambda index: scores[index],
        reverse=True,
    )[:24]
    return sorted(candidates)


def _local_max(scores: list[float], center: int, tolerance: int) -> float:
    start = max(0, center - tolerance)
    end = min(len(scores), center + tolerance + 1)
    return max(scores[start:end]) if end > start else 0.0
