"""
This module contains a db migration.

Migration Name: add_status_index
Migration Version: 20251116173731
"""

from sqlalchemy import text


async def upgrade(c):
    """
    Add index on json_extract(data, '$.status') for better query performance.

    This index improves performance when filtering items by status field,
    which is stored in the JSON data column.
    """
    sql = """
    CREATE INDEX IF NOT EXISTS "history_status" ON "history" (json_extract("data", '$.status'));
    """
    await c.execute(text(sql))


async def downgrade(c):
    """
    Remove the status index.
    """
    sql = """
    DROP INDEX IF EXISTS "history_status";
    """
    await c.execute(text(sql))
