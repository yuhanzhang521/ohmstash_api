"""Baseline schema.

Revision ID: 20260516_0001
Revises:
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    layout_type_enum = postgresql.ENUM(
        "grid",
        "irregular",
        name="layout_type_enum",
        create_type=False,
    )
    stock_mode_enum = postgresql.ENUM(
        "exact",
        "fuzzy",
        name="stock_mode_enum",
        create_type=False,
    )
    quantity_fuzzy_enum = postgresql.ENUM(
        "充足",
        "少量",
        "紧张",
        "未知",
        "用尽",
        name="quantity_fuzzy_enum",
        create_type=False,
    )
    layout_type_enum.create(op.get_bind(), checkfirst=True)
    stock_mode_enum.create(op.get_bind(), checkfirst=True)
    quantity_fuzzy_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"])
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"])
    op.create_index(op.f("ix_api_keys_prefix"), "api_keys", ["prefix"])

    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_auth_users_id"), "auth_users", ["id"])
    op.create_index(op.f("ix_auth_users_username"), "auth_users", ["username"])

    op.create_table(
        "box_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("physical_dimensions", sa.JSON()),
        sa.Column("layout_type", layout_type_enum, nullable=False),
        sa.Column("layout_definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_box_templates_id"), "box_templates", ["id"])

    op.create_table(
        "search_provider_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("api_key", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("extra_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_search_provider_configs_id"), "search_provider_configs", ["id"])
    op.create_index(op.f("ix_search_provider_configs_name"), "search_provider_configs", ["name"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_tags_id"), "tags", ["id"])

    op.create_table(
        "vlm_provider_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=1024)),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("api_key", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("extra_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_vlm_provider_configs_id"), "vlm_provider_configs", ["id"])
    op.create_index(op.f("ix_vlm_provider_configs_name"), "vlm_provider_configs", ["name"])

    op.create_table(
        "attribute_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag_id", "attribute_name", name="uq_tag_attribute_name"),
    )
    op.create_index(op.f("ix_attribute_definitions_id"), "attribute_definitions", ["id"])

    op.create_table(
        "boxes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("readable_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255)),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("printed_label_signature", sa.Text()),
        sa.Column("printed_label_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["template_id"], ["box_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("readable_id"),
    )
    op.create_index(op.f("ix_boxes_id"), "boxes", ["id"])

    op.create_table(
        "components",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("attributes", sa.JSON()),
        sa.Column("display_attribute", sa.String(length=100)),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_components_id"), "components", ["id"])

    op.create_table(
        "components_tags",
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("component_id", "tag_id"),
    )

    op.create_table(
        "recognition_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_kind", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("owner_name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("config_id", sa.Integer()),
        sa.Column("search_provider_config_id", sa.Integer()),
        sa.Column("box_id", sa.Integer()),
        sa.Column("template_id", sa.Integer()),
        sa.Column("layout_type", sa.String(length=32)),
        sa.Column("additional_prompt", sa.Text(), nullable=False),
        sa.Column("overwrite_existing", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("verification_result", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("verification_error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["box_id"], ["boxes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["config_id"], ["vlm_provider_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["search_provider_config_id"], ["search_provider_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["box_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_recognition_sessions_id"), "recognition_sessions", ["id"])
    op.create_index(op.f("ix_recognition_sessions_mode"), "recognition_sessions", ["mode"])
    op.create_index(op.f("ix_recognition_sessions_owner_id"), "recognition_sessions", ["owner_id"])
    op.create_index(op.f("ix_recognition_sessions_owner_kind"), "recognition_sessions", ["owner_kind"])
    op.create_index(op.f("ix_recognition_sessions_status"), "recognition_sessions", ["status"])

    op.create_table(
        "sub_boxes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("box_id", sa.Integer(), nullable=False),
        sa.Column("readable_id", sa.String(length=150), nullable=False),
        sa.Column("position_identifier", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["box_id"], ["boxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("box_id", "position_identifier", name="uq_box_position"),
        sa.UniqueConstraint("readable_id"),
    )
    op.create_index(op.f("ix_sub_boxes_id"), "sub_boxes", ["id"])
    op.create_index(op.f("ix_sub_boxes_readable_id"), "sub_boxes", ["readable_id"])

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sub_box_id", sa.Integer(), nullable=False),
        sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("stock_mode", stock_mode_enum, nullable=False),
        sa.Column("quantity_exact", sa.Integer()),
        sa.Column("quantity_fuzzy", quantity_fuzzy_enum),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "(stock_mode = 'exact' AND quantity_exact IS NOT NULL AND quantity_fuzzy IS NULL) "
            "OR (stock_mode = 'fuzzy' AND quantity_fuzzy IS NOT NULL AND quantity_exact IS NULL)",
            name="check_quantity_mode",
        ),
        sa.ForeignKeyConstraint(["component_id"], ["components.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_box_id"], ["sub_boxes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sub_box_id", "component_id", name="uq_sub_box_component"),
    )
    op.create_index(op.f("ix_inventory_id"), "inventory", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_id"), table_name="inventory")
    op.drop_table("inventory")
    op.drop_index(op.f("ix_sub_boxes_readable_id"), table_name="sub_boxes")
    op.drop_index(op.f("ix_sub_boxes_id"), table_name="sub_boxes")
    op.drop_table("sub_boxes")
    op.drop_index(op.f("ix_recognition_sessions_status"), table_name="recognition_sessions")
    op.drop_index(op.f("ix_recognition_sessions_owner_kind"), table_name="recognition_sessions")
    op.drop_index(op.f("ix_recognition_sessions_owner_id"), table_name="recognition_sessions")
    op.drop_index(op.f("ix_recognition_sessions_mode"), table_name="recognition_sessions")
    op.drop_index(op.f("ix_recognition_sessions_id"), table_name="recognition_sessions")
    op.drop_table("recognition_sessions")
    op.drop_table("components_tags")
    op.drop_index(op.f("ix_components_id"), table_name="components")
    op.drop_table("components")
    op.drop_index(op.f("ix_boxes_id"), table_name="boxes")
    op.drop_table("boxes")
    op.drop_index(op.f("ix_attribute_definitions_id"), table_name="attribute_definitions")
    op.drop_table("attribute_definitions")
    op.drop_index(op.f("ix_vlm_provider_configs_name"), table_name="vlm_provider_configs")
    op.drop_index(op.f("ix_vlm_provider_configs_id"), table_name="vlm_provider_configs")
    op.drop_table("vlm_provider_configs")
    op.drop_index(op.f("ix_tags_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_search_provider_configs_name"), table_name="search_provider_configs")
    op.drop_index(op.f("ix_search_provider_configs_id"), table_name="search_provider_configs")
    op.drop_table("search_provider_configs")
    op.drop_index(op.f("ix_box_templates_id"), table_name="box_templates")
    op.drop_table("box_templates")
    op.drop_index(op.f("ix_auth_users_username"), table_name="auth_users")
    op.drop_index(op.f("ix_auth_users_id"), table_name="auth_users")
    op.drop_table("auth_users")
    op.drop_index(op.f("ix_api_keys_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_id"), table_name="api_keys")
    op.drop_table("api_keys")
    postgresql.ENUM(name="quantity_fuzzy_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="stock_mode_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="layout_type_enum").drop(op.get_bind(), checkfirst=True)
