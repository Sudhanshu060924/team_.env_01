"""baseline: stamp existing Neon schema as initial revision

This migration contains NO DDL.  It exists purely to give Alembic a
known starting point that matches the current Neon database.

Background
----------
VidyaRoom's database was created and evolved before Alembic was introduced.
The schema (tables, columns, indexes, constraints) already matches the
SQLAlchemy models exactly — verified by scripts/audit_schema.py on the
date this revision was created.

Tables present at baseline
--------------------------
  users           -- authentication, name/email/password_hash/role
  lectures        -- lecture sessions, teacher_id FK to users
  lecture_events  -- real-time events per lecture (transcript, OCR, …)
  notes           -- AI-generated notes per lecture, per language
  chat_threads    -- one doubt-chat thread per student per lecture
  chat_messages   -- messages within a chat thread

Extra tables in DB (not managed by Alembic)
--------------------------------------------
  migrations_applied  -- legacy ad-hoc SQL migration tracker (safe to keep)

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    No DDL — the existing Neon database already contains all required tables
    and columns.  This revision simply marks the starting point for future
    Alembic-managed migrations.
    """
    pass


def downgrade() -> None:
    """
    Downgrading the baseline is a no-op.
    We intentionally do NOT drop existing tables on downgrade.
    """
    pass
