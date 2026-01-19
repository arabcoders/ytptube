"""
This module contains a db migration.

Migration Name: add_dl_fields_table
Migration Version: 20260119162444
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
    CREATE TABLE IF NOT EXISTS "dl_fields" (
        "id" INTEGER PRIMARY KEY AUTOINCREMENT,
        "name" TEXT NOT NULL UNIQUE,
        "description" TEXT NOT NULL DEFAULT '',
        "field" TEXT NOT NULL,
        "kind" TEXT NOT NULL DEFAULT 'text',
        "icon" TEXT NOT NULL DEFAULT '',
        "order" INTEGER NOT NULL DEFAULT 0,
        "value" TEXT NOT NULL DEFAULT '',
        "extras" JSON NOT NULL DEFAULT '{}',
        "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        "updated_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
        'CREATE INDEX IF NOT EXISTS "ix_dl_fields_name" ON "dl_fields" ("name");',
        'CREATE INDEX IF NOT EXISTS "ix_dl_fields_order" ON "dl_fields" ("order");',
        'CREATE INDEX IF NOT EXISTS "ix_dl_fields_kind" ON "dl_fields" ("kind");',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "dl_fields";
    """
    await c.execute(text(sql))
