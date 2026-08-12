"""
Simple migration runner for database schema updates.

Migrations are SQL files in backend/migrations/ directory,
named with format: YYYYMMDD_HHMMSS_description.sql
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def run_migrations(engine: AsyncEngine, migrations_dir: str = "migrations") -> None:
    """
    Run all pending migrations.

    Migrations are stored in SQL files in the migrations directory.
    A record of completed migrations is kept in the migrations_applied table.
    """
    from app.database.database import Base

    # Ensure the migrations tracking table exists
    async with engine.begin() as conn:
        # Create migrations tracking table if it doesn't exist
        await conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS migrations_applied (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))

    # Find migration files
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists():
        logger.info(f"No migrations directory found at {migrations_path}")
        return

    migration_files = sorted(migrations_path.glob("*.sql"))
    if not migration_files:
        logger.info(f"No migrations found in {migrations_path}")
        return

    # Get list of already-applied migrations
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT name FROM migrations_applied"))
        applied = {row[0] for row in result.fetchall()}

    # Run pending migrations
    for migration_file in migration_files:
        migration_name = migration_file.name
        if migration_name in applied:
            logger.debug(f"Migration already applied: {migration_name}")
            continue

        logger.info(f"Applying migration: {migration_name}")
        sql_content = migration_file.read_text()

        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql_content))
                # Record the migration
                await conn.execute(
                    text("INSERT INTO migrations_applied (name) VALUES (:name)"),
                    {"name": migration_name},
                )
            logger.info(f"✓ Migration applied: {migration_name}")
        except Exception as exc:
            logger.error(f"✗ Failed to apply migration {migration_name}: {exc}")
            raise
