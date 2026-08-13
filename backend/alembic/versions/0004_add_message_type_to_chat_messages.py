"""add message_type to chat_messages

Separates AI-chat messages from student-teacher doubt messages within
the same thread.

Values:
  "ai_chat" — created by the AI chatbot flow (student question + AI reply)
  "doubt"   — created by the student ↔ teacher doubt flow

NULL rows (created before this migration) are treated as "doubt" by the
service layer so existing data continues to work without a backfill.

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-11 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("message_type", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "message_type")
