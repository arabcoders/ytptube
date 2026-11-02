from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


async def upgrade(c: AsyncConnection) -> None:
    await c.execute(
        text("""
        CREATE TABLE toolbox_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool VARCHAR(64) NOT NULL,
            file TEXT NOT NULL,
            extra JSON NOT NULL DEFAULT '{}',
            status VARCHAR(16) NOT NULL,
            created_at DATETIME NOT NULL,
            started_at DATETIME,
            finished_at DATETIME,
            message TEXT,
            result JSON,
            error TEXT,
            error_code VARCHAR(64),
            log TEXT NOT NULL DEFAULT ''
        )
    """)
    )


async def downgrade(c: AsyncConnection) -> None:
    await c.execute(text("DROP TABLE toolbox_jobs"))
