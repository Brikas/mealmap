# src/db/migrations/versions/2025-11-13-01-16_23f4df2127cb.py
"""enum changes

Revision ID: 23f4df2127cb
Revises: dad2dc48a56a
Create Date: 2025-11-13 01:16:31.219479
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "23f4df2127cb"
down_revision: Union[str, None] = "dad2dc48a56a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRI_STATE = postgresql.ENUM("yes", "no", "unspecified", name="tri_state_enum")

COLUMNS = [
    ("is_vegan", "vegan_status_enum"),
    ("is_halal", "halal_status_enum"),
    ("is_vegetarian", "vegetarian_status_enum"),
    ("is_spicy", "spicy_status_enum"),
    ("is_gluten_free", "gluten_free_status_enum"),
    ("is_dairy_free", "dairy_free_status_enum"),
    ("is_nut_free", "nut_free_status_enum"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Create the new shared enum
    TRI_STATE.create(bind, checkfirst=True)

    # 2) Convert each column to tri_state_enum, mapping 'not specified' -> 'unspecified'
    for col, old_enum in COLUMNS:
        # Drop old default (it references old enum type)
        op.alter_column("meal_review", col, server_default=None)
        # Change type using text cast and mapping
        op.alter_column(
            "meal_review",
            col,
            type_=TRI_STATE,
            postgresql_using=(
                f"REPLACE({col}::text, 'not specified', 'unspecified')::tri_state_enum"
            ),
        )
        # Set new default
        op.alter_column(
            "meal_review",
            col,
            server_default=sa.text("'unspecified'::tri_state_enum"),
        )

    # 3) Drop the now-unused per-column enum types
    for _, old_enum in COLUMNS:
        postgresql.ENUM(name=old_enum).drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()

    # 1) Recreate old enums
    old_enums = {}
    for _, old_enum in COLUMNS:
        e = postgresql.ENUM("no", "not specified", "yes", name=old_enum)
        e.create(bind, checkfirst=True)
        old_enums[old_enum] = e

    # 2) Convert columns back, mapping 'unspecified' -> 'not specified'
    for col, old_enum in COLUMNS:
        op.alter_column("meal_review", col, server_default=None)
        op.alter_column(
            "meal_review",
            col,
            type_=old_enums[old_enum],
            postgresql_using=(
                f"REPLACE({col}::text, 'unspecified', 'not specified')::{old_enum}"
            ),
        )
        op.alter_column(
            "meal_review",
            col,
            server_default=sa.text(f"'not specified'::{old_enum}"),
        )

    # 3) Drop tri_state_enum if unused
    TRI_STATE.drop(bind, checkfirst=True)
