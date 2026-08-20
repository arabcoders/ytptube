"""
This module contains a db migration.

Migration Name: add_session_metadata
Migration Version: 20260820144657
"""

from sqlalchemy import text


async def upgrade(c):
    await c.execute(text('DELETE FROM "sessions"'))
    await c.execute(text('ALTER TABLE "sessions" ADD COLUMN "user_agent" TEXT'))
    await c.execute(text('ALTER TABLE "sessions" ADD COLUMN "ip" TEXT'))


async def downgrade(c):
    await c.execute(text('ALTER TABLE "sessions" DROP COLUMN "ip"'))
    await c.execute(text('ALTER TABLE "sessions" DROP COLUMN "user_agent"'))
