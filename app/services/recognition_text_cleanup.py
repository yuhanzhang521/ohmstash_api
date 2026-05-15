import re
from typing import Any, Optional

VERIFICATION_WARNING_PATTERNS = [
    re.compile(r"未检索到[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"未找到[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"没有可确认[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"无法确认[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"搜索结果不足[^。；;，,\n]*(?:[。；;，,])?"),
    re.compile(r"(?:暂)?保留原标注"),
]
MODEL_CORRECTION_PATTERN = re.compile(
    r"搜索结果指向\s*(?P<target>[^：:。；;，,\n]+)"
    r"(?:[：:]\s*(?P<summary>[^。；;\n]+))?"
    r"[。；;，,\s]*(?P<warning>原始[^。；;\n]*(?:疑似|可能)[^。；;\n]*)"
)
MODEL_MULTI_CORRECTION_PATTERN = re.compile(
    r"搜索结果(?:主要)?指向\s*(?P<targets>[^。；;\n]+?)"
    r"(?:等(?:其他)?型号)?[，,\s]*(?P<warning>原始[^。；;\n]*(?:疑似|可能|误差|抄写|识别)[^。；;\n]*)"
)
MODEL_CORRECTION_TARGET_PATTERN = re.compile(
    r"搜索结果(?:主要)?指向\s*(?P<target>[^：:。；;，,\n]+)"
)
MODEL_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._/-]*\d[A-Za-z0-9._/-]*")
ATTRIBUTE_UNCERTAINTY_PATTERNS = [
    re.compile(r"[（(][^（）()]{0,30}(?:未能|不能|无法|不足|不确定|待确认|不同厂商|版本不一致)[^（）()]{0,40}[）)]"),
    re.compile(r"(?:未能|不能|无法|不足|不确定|待确认|不同厂商|版本不一致)[^。；;，,\n]*"),
]
PHOTO_META_KEYWORDS = (
    "拍摄角度",
    "拍照角度",
    "拍摄方向",
    "拍摄环境",
    "拍摄面",
    "在画面",
    "在图中",
    "标签可见",
    "标签显示",
    "标签含",
    "标签朝向",
    "标签朝",
    "标签清晰",
    "标签上",
    "标签为",
    "标签是",
    "标签写",
    "竖放",
    "横放",
    "竖立",
    "侧立",
    "倒置",
    "正面朝",
    "背面朝",
    "镜头",
    "照片",
    "图片中",
    "字体",
    "字号",
    "印刷字",
    "丝印",
    "丝网",
    "光线",
    "阴影",
    "反光",
    "倾斜放置",
    "斜放",
    "高亮",
    "包装袋",
    "包装上",
    "袋装",
    "纸标签",
)
PHOTO_META_SENTENCE_PATTERN = re.compile(
    r"[^。；;\n]*(?:"
    + "|".join(re.escape(keyword) for keyword in PHOTO_META_KEYWORDS)
    + r")[^。；;\n]*[。；;]?"
)


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
    for pattern in VERIFICATION_WARNING_PATTERNS:
        warnings.extend(match.group(0) for match in pattern.finditer(text))
    if not warnings:
        return None
    warning = " ".join(warnings).strip("。；;，, \n\t")
    return warning or "联网搜索未取得可确认资料，已保留原标注"


def clean_verification_notes(value: Any) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    correction_note, _correction_warning = split_model_correction_note(text)
    if correction_note:
        return strip_photo_meta_phrases(correction_note) or None
    text = remove_multi_correction_warning(text)
    for pattern in VERIFICATION_WARNING_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"(?:联网)?搜索摘要确认[:：]?\s*", "", text)
    text = re.sub(r"联网确认[:：]?\s*", "", text)
    text = strip_photo_meta_phrases(text)
    text = text.strip("。；;，, \n\t")
    return text or None


def strip_photo_meta_phrases(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    cleaned = PHOTO_META_SENTENCE_PATTERN.sub("", text)
    cleaned = re.sub(r"[\s。；;，,]+", lambda match: match.group(0)[0], cleaned)
    return cleaned.strip("。；;，, \n\t")


def split_model_correction_note(value: Any) -> tuple[Optional[str], Optional[str]]:
    text = normalize_search_value(value)
    if not text or "搜索结果指向" not in text:
        return None, None

    match = MODEL_CORRECTION_PATTERN.search(text)
    if not match:
        return None, None

    target = normalize_search_value(match.group("target"))
    summary = normalize_search_value(match.group("summary"))
    warning_tail = normalize_search_value(match.group("warning"))
    note = f"{target}：{summary}" if target and summary else None
    warning = f"搜索结果指向 {target}，{warning_tail}" if target else warning_tail
    return note, warning


def extract_multi_correction_warning(value: Any) -> Optional[str]:
    text = normalize_search_value(value)
    if not text or "搜索结果" not in text:
        return None
    match = MODEL_MULTI_CORRECTION_PATTERN.search(text)
    if not match:
        return None
    target_text = normalize_search_value(match.group("targets")).rstrip("，, ")
    warning_tail = normalize_search_value(match.group("warning"))
    return f"搜索结果主要指向 {target_text}，{warning_tail}" if target_text else warning_tail


def remove_multi_correction_warning(value: str) -> str:
    return MODEL_MULTI_CORRECTION_PATTERN.sub("", value)


def extract_corrected_component_name(
    value: Any,
    *,
    original_name: Optional[str] = None,
) -> Optional[str]:
    text = str(value or "")
    multi_match = MODEL_MULTI_CORRECTION_PATTERN.search(text)
    if multi_match:
        tokens = MODEL_TOKEN_PATTERN.findall(multi_match.group("targets"))
        if tokens:
            return choose_corrected_token(tokens, original_name=original_name)

    match = MODEL_CORRECTION_TARGET_PATTERN.search(text)
    if match:
        target = normalize_search_value(match.group("target"))
        tokens = MODEL_TOKEN_PATTERN.findall(target)
        if tokens:
            return choose_corrected_token(tokens, original_name=original_name)
        return target or None

    if "搜索结果" not in text:
        return None

    tokens = MODEL_TOKEN_PATTERN.findall(text)
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
