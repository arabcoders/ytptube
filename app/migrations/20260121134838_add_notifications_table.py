"""
This module contains a db migration.

Migration Name: add_notifications_table
Migration Version: 20260121134838
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
    CREATE TABLE IF NOT EXISTS "notifications" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL UNIQUE,
        "on" JSON NOT NULL DEFAULT '[]',
        "presets" JSON NOT NULL DEFAULT '[]',
        "enabled" BOOLEAN NOT NULL DEFAULT 1,
        "request_url" TEXT NOT NULL,
        "request_method" TEXT NOT NULL DEFAULT 'POST',
        "request_type" TEXT NOT NULL DEFAULT 'json',
        "request_data_key" TEXT NOT NULL DEFAULT 'data',
        "request_headers" JSON NOT NULL DEFAULT '[]',
        "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
        'CREATE INDEX IF NOT EXISTS "ix_notifications_name" ON "notifications" ("name");',
        'CREATE INDEX IF NOT EXISTS "ix_notifications_enabled" ON "notifications" ("enabled");',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "notifications";
    """
    await c.execute(text(sql))
