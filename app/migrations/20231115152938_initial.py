"""
This module contains a db migration.

Migration Name: initial
Migration Version: 20231115152938
"""


async def upgrade(c):
    sql = """
    CREATE TABLE "history" (
        "id" TEXT PRIMARY KEY UNIQUE NOT NULL,
        "type" TEXT NOT NULL,
        "url" TEXT NOT NULL,
        "data" JSON NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    await c.execute(sql)

    sql = """
    CREATE INDEX "history_type" ON "history" ("type");
    """
    await c.execute(sql)

    sql = """
    CREATE UNIQUE INDEX "history_url" ON "history" ("url");
    """
    await c.execute(sql)

    await c.commit()


async def downgrade(c):
    sql = """
    DROP TABLE IF EXISTS "history";
    """

    await c.execute(sql)
