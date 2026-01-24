"""
This module contains a db migration.

Migration Name: add_tasks_table
Migration Version: 20260124171740
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                folder TEXT NOT NULL DEFAULT '',
                preset TEXT NOT NULL DEFAULT '',
                timer TEXT NOT NULL DEFAULT '',
                template TEXT NOT NULL DEFAULT '',
                cli TEXT NOT NULL DEFAULT '',
                auto_start INTEGER NOT NULL DEFAULT 1,
                handler_enabled INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        'CREATE INDEX IF NOT EXISTS "ix_tasks_name" ON "tasks" ("name")',
        'CREATE INDEX IF NOT EXISTS "ix_tasks_enabled" ON "tasks" ("enabled")',
        'CREATE INDEX IF NOT EXISTS "ix_tasks_timer" ON "tasks" ("timer")',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql: list[str] = [
        'DROP INDEX IF EXISTS "ix_tasks_name"',
        'DROP INDEX IF EXISTS "ix_tasks_enabled"',
        'DROP INDEX IF EXISTS "ix_tasks_timer"',
        'DROP TABLE IF EXISTS "tasks"',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))
