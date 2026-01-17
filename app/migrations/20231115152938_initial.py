"""
This module contains a db migration.

Migration Name: initial
Migration Version: 20231115152938
"""

from sqlalchemy import text


async def upgrade(c):
    sql: list[str] = [
        """
        CREATE TABLE "history" (
            "id" TEXT PRIMARY KEY UNIQUE NOT NULL,
            "type" TEXT NOT NULL,
            "url" TEXT NOT NULL,
            "data" JSON NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        'CREATE INDEX "history_type" ON "history" ("type");',
        'CREATE UNIQUE INDEX "history_url" ON "history" ("url");',
    ]
    for sql_stmt in sql:
        await c.execute(text(sql_stmt))

    await c.commit()


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "history";
    """

    await c.execute(text(sql))
