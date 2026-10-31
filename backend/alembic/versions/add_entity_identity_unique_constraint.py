"""enforce unique entity identity

Revision ID: a4f7c2d91e60
Revises: 9d5e1d520b6e
Create Date: 2026-10-24
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "a4f7c2d91e60"
down_revision: Union[str, Sequence[str], None] = "9d5e1d520b6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Prevent duplicate entities of the same type and canonical value."""
    op.create_unique_constraint(
        "uq_entities_type_canonical_value",
        "entities",
        ["entity_type", "canonical_value"],
    )


def downgrade() -> None:
    """Remove the entity identity uniqueness constraint."""
    op.drop_constraint(
        "uq_entities_type_canonical_value",
        "entities",
        type_="unique",
    )