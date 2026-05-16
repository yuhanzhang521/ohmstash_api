from pathlib import Path
from typing import Iterable

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database import ensure_schema_compatibility

BASELINE_REVISION = "20260516_0001"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"
APPLICATION_TABLES = {
    "api_keys",
    "auth_users",
    "box_templates",
    "search_provider_configs",
    "tags",
    "vlm_provider_configs",
    "attribute_definitions",
    "boxes",
    "components",
    "components_tags",
    "recognition_sessions",
    "sub_boxes",
    "inventory",
}


def run_database_migrations(database_url: str, *, engine: Engine) -> None:
    if _has_existing_schema_without_alembic(engine):
        ensure_schema_compatibility()
        _stamp_database(database_url, BASELINE_REVISION)
    command.upgrade(_build_alembic_config(database_url), "head")


def reset_database_with_migrations(database_url: str, *, engine: Engine) -> None:
    _drop_database_objects(engine)
    command.upgrade(_build_alembic_config(database_url), "head")


def _has_existing_schema_without_alembic(engine: Engine) -> bool:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    return "alembic_version" not in table_names and bool(
        table_names.intersection(APPLICATION_TABLES),
    )


def _stamp_database(database_url: str, revision: str) -> None:
    command.stamp(_build_alembic_config(database_url), revision)


def _build_alembic_config(database_url: str) -> Config:
    config = Config(ALEMBIC_INI_PATH.as_posix())
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _drop_database_objects(engine: Engine) -> None:
    statements = _drop_statements(engine)
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _drop_statements(engine: Engine) -> Iterable[str]:
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        yield f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
    for enum_name in inspector.get_enums():
        name = enum_name["name"].replace('"', '""')
        schema = enum_name.get("schema")
        if schema and schema != "public":
            schema_name = schema.replace('"', '""')
            yield f'DROP TYPE IF EXISTS "{schema_name}"."{name}" CASCADE'
        else:
            yield f'DROP TYPE IF EXISTS "{name}" CASCADE'
