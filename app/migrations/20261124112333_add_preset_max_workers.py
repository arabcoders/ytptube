from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


async def upgrade(c: AsyncConnection) -> None:
    await c.execute(text("ALTER TABLE presets ADD COLUMN max_workers INTEGER NOT NULL DEFAULT 0"))


async def downgrade(c: AsyncConnection) -> None:
    await c.execute(text("ALTER TABLE presets DROP COLUMN max_workers"))
