"""
This module contains a Caribou migration.

Migration Name: add_status_index
Migration Version: 20251116173731
"""

def upgrade(connection):
    """
    Add index on json_extract(data, '$.status') for better query performance.

    This index improves performance when filtering items by status field,
    which is stored in the JSON data column.
    """
    sql = """
    CREATE INDEX IF NOT EXISTS "history_status" ON "history" (json_extract("data", '$.status'));
    """
    connection.execute(sql)

def downgrade(connection):
    """
    Remove the status index.
    """
    sql = """
    DROP INDEX IF EXISTS "history_status";
    """
    connection.execute(sql)
