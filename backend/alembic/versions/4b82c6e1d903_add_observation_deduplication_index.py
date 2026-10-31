"""prevent duplicate observations, including null timestamps

Revision ID: 4b82c6e1d903
Revises: a4f7c2d91e60
Create Date: 2026-10-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "4b82c6e1d903"
down_revision: Union[str, Sequence[str], None] = "a4f7c2d91e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_observations_source_hash_observed_at"


def upgrade() -> None:
    """Prevent duplicate observation identity keys at database level."""
    op.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON observations (
            source_id,
            content_sha256,
            observed_at
        ) NULLS NOT DISTINCT
        """
    )


def downgrade() -> None:
    """Remove the observation deduplication index."""
    op.drop_index(INDEX_NAME, table_name="observations")