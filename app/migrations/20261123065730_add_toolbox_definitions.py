from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


async def _recreate_jobs(c: AsyncConnection, *, upgrade: bool) -> None:
    await c.execute(text("DROP TABLE toolbox_jobs"))
    tool_type = "INTEGER" if upgrade else "VARCHAR(64)"
    await c.execute(
        text(f"""
        CREATE TABLE toolbox_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool {tool_type} NOT NULL,
            file TEXT NOT NULL,
            extra JSON NOT NULL DEFAULT '{{}}',
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


async def upgrade(c: AsyncConnection) -> None:
    await _recreate_jobs(c, upgrade=True)
    await c.execute(
        text("""
        CREATE TABLE toolbox_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            default_key TEXT UNIQUE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            output_extension TEXT NOT NULL,
            supports_overwrite BOOLEAN NOT NULL DEFAULT 0,
            command JSON NOT NULL DEFAULT '[]',
            env JSON NOT NULL DEFAULT '{}',
            params JSON NOT NULL DEFAULT '{}',
            extras JSON NOT NULL DEFAULT '{}'
        )
        """)
    )


async def downgrade(c: AsyncConnection) -> None:
    await _recreate_jobs(c, upgrade=False)
    await c.execute(text("DROP TABLE toolbox_definitions"))
