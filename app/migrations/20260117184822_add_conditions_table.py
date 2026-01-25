"""
This module contains a db migration.

Migration Name: add_conditions_table
Migration Version: 20260117184822
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
    CREATE TABLE IF NOT EXISTS "conditions" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL UNIQUE,
        "filter" TEXT NOT NULL,
        "cli" TEXT NOT NULL DEFAULT '',
        "extras" JSON NOT NULL DEFAULT '{}',
        "enabled" INTEGER NOT NULL DEFAULT 1,
        "priority" INTEGER NOT NULL DEFAULT 0,
        "description" TEXT NOT NULL DEFAULT '',
        "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
        'CREATE INDEX IF NOT EXISTS "ix_conditions_name" ON "conditions" ("name");',
        'CREATE INDEX IF NOT EXISTS "ix_conditions_enabled" ON "conditions" ("enabled");',
        'CREATE INDEX IF NOT EXISTS "ix_conditions_priority" ON "conditions" ("priority");',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "conditions";
    """
    await c.execute(text(sql))
