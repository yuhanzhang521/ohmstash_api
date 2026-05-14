import unicodedata


BOX_NAME_MAX_DISPLAY_WIDTH = 14


def compute_display_width(value: str) -> int:
    width = 0
    for char in str(value or ""):
        east_asian_width = unicodedata.east_asian_width(char)
        if east_asian_width in ("F", "W", "A"):
            width += 2
        else:
            width += 1
    return width


def is_box_name_within_limit(value: str | None) -> bool:
    if value is None:
        return True
    return compute_display_width(value) <= BOX_NAME_MAX_DISPLAY_WIDTH


def truncate_to_display_width(value: str, max_width: int = BOX_NAME_MAX_DISPLAY_WIDTH) -> str:
    width = 0
    result_chars = []
    for char in str(value or ""):
        east_asian_width = unicodedata.east_asian_width(char)
        char_width = 2 if east_asian_width in ("F", "W", "A") else 1
        if width + char_width > max_width:
            break
        result_chars.append(char)
        width += char_width
    return "".join(result_chars)

