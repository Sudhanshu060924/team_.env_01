"""
Schema Audit Script
-------------------
Compares the actual Neon database schema against SQLAlchemy models.
Prints a detailed diff per table (ASCII-only output for Windows terminals).

Run from backend/:
    python scripts/audit_schema.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# psycopg v3 requires SelectorEventLoop on Windows (same as main app)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool

from app.config import get_settings
from app.database.database import Base
import app.database.models  # noqa: F401 -- registers all models


def _coerce_async_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


async def audit():
    url = _coerce_async_url(get_settings().DATABASE_URL)
    engine = create_async_engine(url, poolclass=pool.NullPool, echo=False)

    async with engine.connect() as conn:
        # 1. Actual tables in the database
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        db_tables = {row[0] for row in result.fetchall()}

        # 2. Actual columns per table
        result = await conn.execute(text("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """))
        db_columns: dict[str, dict[str, dict]] = {}
        for row in result.fetchall():
            tname, cname, dtype, nullable, default = row
            db_columns.setdefault(tname, {})[cname] = {
                "type": dtype,
                "nullable": nullable,
                "default": default,
            }

        # 3. Actual constraints
        result = await conn.execute(text("""
            SELECT tc.table_name, tc.constraint_name, tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """))
        db_constraints: dict[str, list[str]] = {}
        for row in result.fetchall():
            tname, cname, ctype = row
            db_constraints.setdefault(tname, []).append(f"{ctype}: {cname}")

        # 4. Actual indexes
        result = await conn.execute(text("""
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """))
        db_indexes: dict[str, list[str]] = {}
        for row in result.fetchall():
            tname, iname = row
            db_indexes.setdefault(tname, []).append(iname)

    await engine.dispose()

    # 5. Compare model metadata against DB
    model_tables = set(Base.metadata.tables.keys())
    sep = "=" * 70

    lines = [
        sep,
        "SCHEMA AUDIT -- VidyaRoom Neon Database",
        sep,
        "",
        "--- Tables ---",
        f"  In DB only   : {sorted(db_tables - model_tables)}",
        f"  In model only: {sorted(model_tables - db_tables)}",
        f"  In both      : {sorted(db_tables & model_tables)}",
    ]

    for table_name in sorted(model_tables):
        model_tbl = Base.metadata.tables[table_name]
        model_cols = {c.name for c in model_tbl.columns}
        db_cols = set(db_columns.get(table_name, {}).keys())

        missing_in_db = model_cols - db_cols
        extra_in_db = db_cols - model_cols

        lines.append("")
        lines.append(f"--- TABLE: {table_name} ---")

        if table_name not in db_tables:
            lines.append("  *** TABLE DOES NOT EXIST IN DATABASE -- needs CREATE ***")
            lines.append(f"  Model columns: {sorted(model_cols)}")
            continue

        lines.append(f"  DB columns   : {sorted(db_cols)}")
        lines.append(f"  Model columns: {sorted(model_cols)}")

        if missing_in_db:
            lines.append(f"  MISSING in DB: {sorted(missing_in_db)}  <-- ACTION REQUIRED")
        if extra_in_db:
            lines.append(f"  EXTRA in DB  : {sorted(extra_in_db)}  <-- informational only")
        if not missing_in_db and not extra_in_db:
            lines.append("  Column match : OK")

        lines.append("  Column details (name | db_type | nullable | default):")
        for col in sorted(model_tbl.columns, key=lambda c: c.name):
            db_info = db_columns.get(table_name, {}).get(col.name)
            if db_info:
                lines.append(
                    f"    {col.name:<30} type={db_info['type']:<20} "
                    f"nullable={db_info['nullable']}  default={db_info['default']}"
                )
            else:
                lines.append(f"    {col.name:<30} *** NOT IN DATABASE ***")

        clist = db_constraints.get(table_name, [])
        lines.append(f"  DB constraints : {clist}")

        ilist = db_indexes.get(table_name, [])
        lines.append(f"  DB indexes     : {ilist}")

    lines.append("")
    lines.append("--- Extra tables in DB not in models ---")
    for tname in sorted(db_tables - model_tables):
        lines.append(f"  {tname}: columns={sorted(db_columns.get(tname, {}).keys())}")

    lines.append("")
    lines.append(sep)
    lines.append("Audit complete.")
    lines.append(sep)

    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(audit())
