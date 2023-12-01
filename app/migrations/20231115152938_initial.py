"""
This module contains a Caribou migration.

Migration Name: initial
Migration Version: 20231115152938
"""


def upgrade(connection):
    sql = """
    CREATE TABLE "history" (
        "id" TEXT PRIMARY KEY UNIQUE NOT NULL,
        "type" TEXT NOT NULL,
        "url" TEXT NOT NULL,
        "data" JSON NOT NULL,
        "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    connection.execute(sql)

    sql = """
    CREATE INDEX "history_type" ON "history" ("type");
    """
    connection.execute(sql)

    sql = """
    CREATE UNIQUE INDEX "history_url" ON "history" ("url");
    """
    connection.execute(sql)

    connection.commit()


def downgrade(connection):
    sql = """
    DROP TABLE IF EXISTS "history";
    """

    connection.execute(sql)
