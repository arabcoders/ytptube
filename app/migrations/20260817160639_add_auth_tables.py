"""
This module contains a db migration.

Migration Name: add_auth_tables
Migration Version: 20260817160639
"""

from sqlalchemy import text


async def upgrade(c):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        'CREATE INDEX IF NOT EXISTS "ix_users_username" ON "users" ("username")',
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_digest TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        'CREATE INDEX IF NOT EXISTS "ix_sessions_token_digest" ON "sessions" ("token_digest")',
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            key_digest TEXT NOT NULL UNIQUE,
            hint TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at DATETIME
        )
        """,
        'CREATE INDEX IF NOT EXISTS "ix_api_keys_key_digest" ON "api_keys" ("key_digest")',
        'CREATE INDEX IF NOT EXISTS "ix_api_keys_user_id" ON "api_keys" ("user_id")',
    ]
    for statement in statements:
        await c.execute(text(statement))


async def downgrade(c):
    for statement in (
        'DROP INDEX IF EXISTS "ix_api_keys_user_id"',
        'DROP INDEX IF EXISTS "ix_api_keys_key_digest"',
        'DROP TABLE IF EXISTS "api_keys"',
        'DROP INDEX IF EXISTS "ix_sessions_token_digest"',
        'DROP TABLE IF EXISTS "sessions"',
        'DROP INDEX IF EXISTS "ix_users_username"',
        'DROP TABLE IF EXISTS "users"',
    ):
        await c.execute(text(statement))
