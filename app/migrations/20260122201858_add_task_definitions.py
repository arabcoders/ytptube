"""
This module contains a db migration.

Migration Name: add_task_definitions
Migration Version: 20260122201858
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
    CREATE TABLE IF NOT EXISTS "task_definitions" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL UNIQUE,
        "priority" INTEGER NOT NULL DEFAULT 0,
        "enabled" BOOLEAN NOT NULL DEFAULT 1,
        "match_url" JSON NOT NULL,
        "definition" JSON NOT NULL DEFAULT '{}',
        "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
        'CREATE INDEX IF NOT EXISTS "ix_task_definitions_name" ON "task_definitions" ("name");',
        'CREATE INDEX IF NOT EXISTS "ix_task_definitions_priority" ON "task_definitions" ("priority");',
        'CREATE INDEX IF NOT EXISTS "ix_task_definitions_match_url" ON "task_definitions" ("match_url");',
        'CREATE INDEX IF NOT EXISTS "ix_task_definitions_enabled" ON "task_definitions" ("enabled");',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "task_definitions";
    """
    await c.execute(text(sql))
