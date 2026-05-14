from collections import Counter
from typing import Any, List

from sqlalchemy.orm import Session

from app import models
from app.services.box_name_rules import (
    BOX_NAME_MAX_DISPLAY_WIDTH,
    compute_display_width,
    is_box_name_within_limit,
)

MAX_LABEL_SUMMARY_LINES = 6
MAX_LABEL_SUMMARY_CHARS = 10

__all__ = [
    "BOX_NAME_MAX_DISPLAY_WIDTH",
    "MAX_LABEL_SUMMARY_CHARS",
    "MAX_LABEL_SUMMARY_LINES",
    "build_box_label_summary_lines",
    "compute_box_category_summary",
    "compute_display_width",
    "format_template_label",
    "generate_next_box_readable_id",
    "is_box_name_within_limit",
]


def generate_next_box_readable_id(db: Session) -> str:
    latest_box = db.query(models.Box).order_by(models.Box.id.desc()).first()
    next_number = (latest_box.id + 1) if latest_box else 1
    while True:
        readable_id = f"BOX-{next_number:04d}"
        exists = (
            db.query(models.Box)
            .filter(models.Box.readable_id == readable_id)
            .first()
        )
        if not exists:
            return readable_id
        next_number += 1


def format_template_label(
    *,
    template_name: str,
    layout_type: str | None,
    layout_definition: dict[str, Any] | None,
) -> str:
    return template_name


def compute_box_category_summary(box: models.Box) -> List[str]:
    labels: Counter[str] = Counter()
    fallback_names: Counter[str] = Counter()

    for sub_box in box.sub_boxes:
        for inventory_item in sub_box.inventory:
            component = inventory_item.component
            if not component:
                continue
            fallback_names[_shorten_label_line(component.name)] += 1
            for tag in component.tags:
                root_name = tag.name.split("/", 1)[0].strip()
                if root_name:
                    labels[_shorten_label_line(root_name)] += 1

    source = labels if labels else fallback_names
    if not source:
        return []

    ordered_lines = [
        label
        for label, _count in source.most_common(MAX_LABEL_SUMMARY_LINES)
        if label
    ]
    return ordered_lines


def build_box_label_summary_lines(box: models.Box) -> List[str]:
    ordered_lines = compute_box_category_summary(box)
    if not ordered_lines:
        return _center_label_lines(["空盒"])
    return _center_label_lines(ordered_lines)


def _center_label_lines(lines: List[str]) -> List[str]:
    trimmed_lines = [
        _shorten_label_line(line)
        for line in lines[:MAX_LABEL_SUMMARY_LINES]
        if line.strip()
    ]
    if len(trimmed_lines) >= MAX_LABEL_SUMMARY_LINES:
        return trimmed_lines[:MAX_LABEL_SUMMARY_LINES]

    blank_count = MAX_LABEL_SUMMARY_LINES - len(trimmed_lines)
    top_blank_count = blank_count // 2
    bottom_blank_count = blank_count - top_blank_count
    return (
        [""] * top_blank_count
        + trimmed_lines
        + [""] * bottom_blank_count
    )


def _shorten_label_line(value: str) -> str:
    compact_value = " ".join(str(value).split())
    return compact_value[:MAX_LABEL_SUMMARY_CHARS]

