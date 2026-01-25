"""
This module contains a db migration.

Migration Name: add_presets_table
Migration Version: 20260125125900
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            folder TEXT NOT NULL DEFAULT '',
            template TEXT NOT NULL DEFAULT '',
            cookies TEXT NOT NULL DEFAULT '',
            cli TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        'CREATE INDEX IF NOT EXISTS "ix_presets_name" ON "presets" ("name")',
        'CREATE INDEX IF NOT EXISTS "ix_presets_is_default" ON "presets" ("is_default")',
        'CREATE INDEX IF NOT EXISTS "ix_presets_priority" ON "presets" ("priority")',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql: list[str] = [
        'DROP INDEX IF EXISTS "ix_presets_name"',
        'DROP INDEX IF EXISTS "ix_presets_is_default"',
        'DROP INDEX IF EXISTS "ix_presets_priority"',
        'DROP TABLE IF EXISTS "presets"',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))
