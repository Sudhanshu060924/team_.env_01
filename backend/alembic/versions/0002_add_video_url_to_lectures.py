"""add video_url and cloudinary_public_id to lectures

Adds two nullable columns to the existing `lectures` table for Cloudinary
video storage.  No data is lost; the columns default to NULL for all
pre-existing lecture rows.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add video_url and cloudinary_public_id to the lectures table."""
    op.add_column(
        "lectures",
        sa.Column("video_url", sa.String(), nullable=True),
    )
    op.add_column(
        "lectures",
        sa.Column("cloudinary_public_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove video_url and cloudinary_public_id from the lectures table."""
    op.drop_column("lectures", "cloudinary_public_id")
    op.drop_column("lectures", "video_url")
