import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

CLEANUP_RULES_PATH = Path(__file__).with_name("recognition_text_cleanup_rules.json")


@lru_cache(maxsize=1)
def load_cleanup_rules() -> dict[str, Any]:
    return json.loads(CLEANUP_RULES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_compiled_rules() -> dict[str, Any]:
    rules = load_cleanup_rules()
    delimiters = rules["sentence_delimiters"]
    warning_patterns = [
        re.compile(rf"{re.escape(prefix)}[^{delimiters}\n]*(?:[{delimiters}])?")
        for prefix in rules["verification_warning_prefixes"]
    ]
    warning_patterns.extend(
        re.compile(pattern) for pattern in rules["verification_warning_phrases"]
    )
    photo_meta_sentence_pattern = re.compile(
        rf"[^。；;\n]*(?:"
        + "|".join(re.escape(keyword) for keyword in rules["photo_meta_keywords"])
        + rf")[^。；;\n]*[。；;]?"
    )
    return {
        "verification_warning_patterns": warning_patterns,
        "model_correction_pattern": re.compile(rules["model_correction_pattern"]),
        "model_multi_correction_pattern": re.compile(rules["model_multi_correction_pattern"]),
        "model_correction_target_pattern": re.compile(rules["model_correction_target_pattern"]),
        "model_token_pattern": re.compile(rules["model_token_pattern"]),
        "attribute_uncertainty_patterns": [
            re.compile(pattern) for pattern in rules["attribute_uncertainty_patterns"]
        ],
        "photo_meta_sentence_pattern": photo_meta_sentence_pattern,
    }


ATTRIBUTE_UNCERTAINTY_PATTERNS = get_compiled_rules()["attribute_uncertainty_patterns"]


def extract_verification_warning(value: Any) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    _note, correction_warning = split_model_correction_note(text)
    if correction_warning:
        return correction_warning
    multi_correction_warning = extract_multi_correction_warning(text)
    if multi_correction_warning:
        return multi_correction_warning
    warnings: list[str] = []
    for pattern in get_compiled_rules()["verification_warning_patterns"]:
        warnings.extend(match.group(0) for match in pattern.finditer(text))
    if not warnings:
        return None
    rules = load_cleanup_rules()
    warning = " ".join(warnings).strip(rules["trim_characters"])
    return warning or rules["fallback_warning"]


def clean_verification_notes(value: Any) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    correction_note, _correction_warning = split_model_correction_note(text)
    if correction_note:
        return strip_photo_meta_phrases(correction_note) or None
    text = remove_multi_correction_warning(text)
    compiled_rules = get_compiled_rules()
    for pattern in compiled_rules["verification_warning_patterns"]:
        text = pattern.sub("", text)
    for pattern in load_cleanup_rules()["verification_note_prefix_patterns"]:
        text = re.sub(pattern, "", text)
    text = strip_photo_meta_phrases(text)
    text = text.strip(load_cleanup_rules()["trim_characters"])
    return text or None


def strip_photo_meta_phrases(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    cleaned = get_compiled_rules()["photo_meta_sentence_pattern"].sub("", text)
    cleaned = re.sub(r"[\s。；;，,]+", lambda match: match.group(0)[0], cleaned)
    return cleaned.strip(load_cleanup_rules()["trim_characters"])


def split_model_correction_note(value: Any) -> tuple[Optional[str], Optional[str]]:
    rules = load_cleanup_rules()
    text = normalize_search_value(value)
    if not text or rules["model_correction_target_prefix"] not in text:
        return None, None

    match = get_compiled_rules()["model_correction_pattern"].search(text)
    if not match:
        return None, None

    target = normalize_search_value(match.group("target"))
    summary = normalize_search_value(match.group("summary"))
    warning_tail = normalize_search_value(match.group("warning"))
    note = f"{target}：{summary}" if target and summary else None
    warning = (
        f"{rules['model_correction_target_prefix']} {target}，{warning_tail}"
        if target
        else warning_tail
    )
    return note, warning


def extract_multi_correction_warning(value: Any) -> Optional[str]:
    rules = load_cleanup_rules()
    text = normalize_search_value(value)
    if not text or rules["model_correction_trigger"] not in text:
        return None
    match = get_compiled_rules()["model_multi_correction_pattern"].search(text)
    if not match:
        return None
    target_text = normalize_search_value(match.group("targets")).rstrip("，, ")
    warning_tail = normalize_search_value(match.group("warning"))
    return (
        f"{rules['model_correction_main_prefix']} {target_text}，{warning_tail}"
        if target_text
        else warning_tail
    )


def remove_multi_correction_warning(value: str) -> str:
    return get_compiled_rules()["model_multi_correction_pattern"].sub("", value)


def extract_corrected_component_name(
    value: Any,
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    rules = load_cleanup_rules()
    text = str(value or "")
    compiled_rules = get_compiled_rules()
    multi_match = compiled_rules["model_multi_correction_pattern"].search(text)
    if multi_match:
        tokens = compiled_rules["model_token_pattern"].findall(multi_match.group("targets"))
        if tokens:
            return choose_corrected_token(tokens, original_name=original_name)

    match = compiled_rules["model_correction_target_pattern"].search(text)
    if match:
        target = normalize_search_value(match.group("target"))
        tokens = compiled_rules["model_token_pattern"].findall(target)
        if tokens:
            return choose_corrected_token(tokens, original_name=original_name)
        return target or None

    if rules["model_correction_trigger"] not in text:
        return None

    tokens = compiled_rules["model_token_pattern"].findall(text)
    if tokens:
        return choose_corrected_token(tokens, original_name=original_name)
    return None


def choose_corrected_token(
    tokens: list[str],
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    unique_tokens: list[str] = []
    for token in tokens:
        normalized_token = token.strip(".,;:，；：。")
        if normalized_token and normalized_token not in unique_tokens:
            unique_tokens.append(normalized_token)
    if not unique_tokens:
        return None

    original = normalize_search_value(original_name).upper()
    if original:
        for token in unique_tokens:
            candidate = token.upper()
            if len(candidate) == len(original) and candidate[1:] == original[1:]:
                return token
        close_tokens = [
            token
            for token in unique_tokens
            if edit_distance(token.upper(), original) <= 1
            and token.upper() != original
        ]
        if close_tokens:
            return close_tokens[-1]
    return unique_tokens[-1]


def edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def normalize_search_value(value: Any) -> str:
    return str(value or "").strip()
