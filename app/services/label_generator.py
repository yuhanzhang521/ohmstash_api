from html import escape
from typing import Any, List, Optional

from app.services.box_labeling import format_template_label


def generate_box_label_svg(
    *,
    readable_id: str,
    template_name: str,
    layout_type: Optional[str] = None,
    layout_definition: Optional[dict[str, Any]] = None,
    box_name: str | None = None,
    summary_lines: Optional[List[str]] = None,
) -> str:
    template_label = format_template_label(
        template_name=template_name,
        layout_type=layout_type,
        layout_definition=layout_definition,
    )
    content_lines = summary_lines or ["", "", "空盒", "", "", ""]
    summary_svg = "\n".join(
        _render_summary_line(line=line, index=index)
        for index, line in enumerate(content_lines[:6])
    )
    datamatrix_svg = _generate_datamatrix_preview_svg(readable_id)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="30mm" height="15mm" '
        'viewBox="0 0 300 150">\n'
        '<rect width="300" height="150" fill="#fff"/>\n'
        '<rect x="2" y="2" width="296" height="146" fill="none" '
        'stroke="#111" stroke-width="1"/>\n'
        f'<text x="10" y="28" font-family="Arial, sans-serif" font-size="28" '
        f'font-weight="700">{escape(readable_id[:18])}</text>\n'
        f'<text x="10" y="52" font-family="Arial, sans-serif" font-size="20">'
        f'{escape((box_name or "未命名")[:14])}</text>\n'
        f'<text x="10" y="76" font-family="Arial, sans-serif" font-size="20">'
        f'{escape(template_label[:14])}</text>\n'
        f'<g transform="translate(10 90)">{datamatrix_svg}</g>\n'
        f'{summary_svg}\n'
        "</svg>\n"
    )


def _render_summary_line(*, line: str, index: int) -> str:
    y = 24 + index * 20
    return (
        f'<text x="224" y="{y}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="18">'
        f'{escape(line)}</text>'
    )


def _generate_datamatrix_preview_svg(value: str) -> str:
    cols = 24
    rows = 10
    cell_size = 5
    elements = [
        '<rect x="0" y="0" width="120" height="50" fill="#fff" '
        'stroke="#111" stroke-width="1"/>'
    ]
    seed = sum(ord(char) * (index + 1) for index, char in enumerate(value))
    for row in range(rows):
        for col in range(cols):
            is_border = row in (0, rows - 1) or col in (0, cols - 1)
            is_dark = is_border or ((row * 17 + col * 31 + seed) % 7 in (0, 2, 5))
            if is_dark:
                elements.append(
                    f'<rect x="{col * cell_size}" y="{row * cell_size}" '
                    f'width="{cell_size}" height="{cell_size}" fill="#111"/>'
                )
    return "".join(elements)
