from sqlalchemy import create_engine, inspect

from app.core.migrations import reset_database_with_migrations


def test_alembic_upgrade_creates_baseline_schema(test_database_url: str) -> None:
    engine = create_engine(test_database_url, pool_pre_ping=True)

    reset_database_with_migrations(test_database_url, engine=engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert "alembic_version" in table_names
    assert "components" in table_names
    assert "recognition_sessions" in table_names
    assert "display_attribute" in {
        column["name"] for column in inspector.get_columns("components")
    }
