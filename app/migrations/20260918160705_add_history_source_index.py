"""
This module contains a db migration.

Migration Name: add_history_source_index
Migration Version: 20260918160705
"""

from sqlalchemy import text


async def upgrade(c):
    await c.execute(
        text(
            'CREATE INDEX IF NOT EXISTS "history_type_source_id" '
            'ON "history" ("type", CAST(json_extract("data", \'$.extras.source_id\') AS INTEGER));'
        )
    )


async def downgrade(c):
    await c.execute(text('DROP INDEX IF EXISTS "history_type_source_id";'))
