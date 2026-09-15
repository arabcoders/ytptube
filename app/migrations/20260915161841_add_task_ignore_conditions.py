"""
This module contains a db migration.

Migration Name: add_task_ignore_conditions
Migration Version: 20260915161841
"""

from sqlalchemy import text


async def upgrade(c):
    await c.execute(text("ALTER TABLE tasks ADD COLUMN ignore_conditions TEXT NOT NULL DEFAULT '[]'"))


async def downgrade(c):
    await c.execute(text("ALTER TABLE tasks DROP COLUMN ignore_conditions"))
