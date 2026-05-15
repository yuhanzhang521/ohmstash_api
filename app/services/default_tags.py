import json
from functools import lru_cache
from pathlib import Path

from app import schemas

DEFAULT_TAGS_PATH = Path(__file__).with_name("default_tags.json")


@lru_cache(maxsize=1)
def load_default_tags() -> tuple[schemas.TagCreate, ...]:
    payload = json.loads(DEFAULT_TAGS_PATH.read_text(encoding="utf-8"))
    return tuple(schemas.TagCreate(**item) for item in payload)
