from sqlalchemy import create_engine, inspect, text
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
    if "components" not in inspector.get_table_names():
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

    _schema_compatibility_checked = True
