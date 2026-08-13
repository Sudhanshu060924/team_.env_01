"""add lecture_ratings table

A dedicated table for student 1–5 star ratings + optional written feedback
for a lecture. Completely separate from chat_messages (Student ↔ Teacher
doubts) and AI chatbot history.

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-12 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lecture_ratings",
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
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("lecture_id", "student_id", name="uq_lecture_ratings_lecture_student"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_lecture_ratings_range"),
    )
    op.create_index("ix_lecture_ratings_lecture_id", "lecture_ratings", ["lecture_id"])
    op.create_index("ix_lecture_ratings_student_id", "lecture_ratings", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_lecture_ratings_student_id", table_name="lecture_ratings")
    op.drop_index("ix_lecture_ratings_lecture_id", table_name="lecture_ratings")
    op.drop_table("lecture_ratings")
