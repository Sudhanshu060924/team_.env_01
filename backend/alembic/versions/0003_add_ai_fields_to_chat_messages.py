"""add detected_topic and ai_answer to chat_messages

Phase 9: AI chatbot fields.
  - detected_topic: the lecture topic this question was classified under (or "Other")
  - ai_answer:      the AI-generated answer text (same as content for AI reply messages)

Both columns are nullable — existing chat messages that predate Phase 9
(teacher replies or plain student messages) will have NULL values.

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-10 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add detected_topic and ai_answer to the chat_messages table."""
    op.add_column(
        "chat_messages",
        sa.Column("detected_topic", sa.String(), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("ai_answer", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove detected_topic and ai_answer from the chat_messages table."""
    op.drop_column("chat_messages", "ai_answer")
    op.drop_column("chat_messages", "detected_topic")
