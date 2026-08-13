"""add playback_analytics table

Stores batched video playback events per student per lecture.
One upserted row per (lecture_id, student_id) — updated on each flush.

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-13 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

# revision identifiers
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "playback_analytics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "lecture_id",
            sa.String(),
            sa.ForeignKey("lectures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Aggregate counters
        sa.Column("play_count",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pause_count",   sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rewind_count",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forward_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replay_count",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seek_count",    sa.Integer(), nullable=False, server_default="0"),
        # Watch time in seconds
        sa.Column("total_watch_seconds", sa.Float(), nullable=False, server_default="0"),
        # Completion (0–100)
        sa.Column("completion_pct", sa.Float(), nullable=False, server_default="0"),
        # Revisit heatmap: list of {start, end, event_type, count} segments
        sa.Column("revisit_segments", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "lecture_id", "student_id",
            name="uq_playback_analytics_lecture_student",
        ),
    )
    op.create_index(
        "ix_playback_analytics_lecture_id",
        "playback_analytics", ["lecture_id"],
    )
    op.create_index(
        "ix_playback_analytics_student_id",
        "playback_analytics", ["student_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_playback_analytics_student_id",  table_name="playback_analytics")
    op.drop_index("ix_playback_analytics_lecture_id",  table_name="playback_analytics")
    op.drop_table("playback_analytics")
