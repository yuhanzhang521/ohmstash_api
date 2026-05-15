from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


if not settings.DATABASE_URL:
    raise ValueError("No DATABASE_URL found in environment variables")

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

_schema_compatibility_checked = False


def ensure_schema_compatibility() -> None:
    global _schema_compatibility_checked
    if _schema_compatibility_checked:
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "components" not in table_names:
        return

    component_columns = {
        column["name"] for column in inspector.get_columns("components")
    }
    if "display_attribute" not in component_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE components "
                    "ADD COLUMN display_attribute VARCHAR(100)"
                )
            )

    if "boxes" in table_names:
        box_columns = {
            column["name"] for column in inspector.get_columns("boxes")
        }
        if "printed_label_signature" not in box_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE boxes ADD COLUMN printed_label_signature TEXT")
                )
        if "printed_label_at" not in box_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE boxes "
                        "ADD COLUMN printed_label_at TIMESTAMP WITH TIME ZONE"
                    )
                )

    if "recognition_sessions" in table_names:
        _ensure_recognition_session_foreign_keys(inspector)

    _schema_compatibility_checked = True


def _ensure_recognition_session_foreign_keys(inspector: Inspector) -> None:
    existing_foreign_keys = {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys("recognition_sessions")
    }
    foreign_key_statements = {
        "fk_recognition_sessions_config_id": (
            "ALTER TABLE recognition_sessions "
            "ADD CONSTRAINT fk_recognition_sessions_config_id "
            "FOREIGN KEY (config_id) REFERENCES vlm_provider_configs(id) "
            "ON DELETE SET NULL"
        ),
        "fk_recognition_sessions_search_provider_config_id": (
            "ALTER TABLE recognition_sessions "
            "ADD CONSTRAINT fk_recognition_sessions_search_provider_config_id "
            "FOREIGN KEY (search_provider_config_id) "
            "REFERENCES search_provider_configs(id) ON DELETE SET NULL"
        ),
        "fk_recognition_sessions_box_id": (
            "ALTER TABLE recognition_sessions "
            "ADD CONSTRAINT fk_recognition_sessions_box_id "
            "FOREIGN KEY (box_id) REFERENCES boxes(id) ON DELETE SET NULL"
        ),
        "fk_recognition_sessions_template_id": (
            "ALTER TABLE recognition_sessions "
            "ADD CONSTRAINT fk_recognition_sessions_template_id "
            "FOREIGN KEY (template_id) REFERENCES box_templates(id) ON DELETE SET NULL"
        ),
    }
    for foreign_key_name, statement in foreign_key_statements.items():
        if foreign_key_name not in existing_foreign_keys:
            with engine.begin() as connection:
                connection.execute(text(statement))
