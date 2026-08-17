from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from Crypto.Protocol.KDF import bcrypt, bcrypt_check
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.features.core.deps import get_session
from app.library.cache import Cache
from app.library.config import Config
from app.library.Services import Services
from app.library.Singleton import Singleton
from app.library.sqlite_store import SqliteStore

SESSION_DAYS = 7
BCRYPT_COST = 12
WS_TICKET_TTL = 30
LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 60


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _password_hash(password: str) -> str:
    if "\x00" in password or len(password.encode()) > 72:
        msg = "Password must be between 1 and 72 UTF-8 bytes and cannot contain NUL bytes."
        raise ValueError(msg)
    return bcrypt(password.encode(), BCRYPT_COST).decode("ascii")


def _password_matches(password: str, stored: str) -> bool:
    try:
        if "\x00" in password or len(password.encode()) > 72:
            return False
        bcrypt_check(password.encode(), stored.encode("ascii"))
        return True
    except (ValueError, TypeError, UnicodeError):
        return False


async def password_hash(password: str) -> str:
    return await asyncio.to_thread(_password_hash, password)


async def password_matches(password: str, stored: str) -> bool:
    return await asyncio.to_thread(_password_matches, password, stored)


class AuthService(metaclass=Singleton):
    @staticmethod
    def get_instance() -> AuthService:
        return AuthService()

    def attach(self, _app) -> None:
        Services.get_instance().add("auth", self)
        _app.on_startup.append(self.startup)

    async def startup(self, _app) -> None:
        await SqliteStore.get_instance().get_connection()
        await self.bootstrap()

    async def bootstrap(self) -> None:
        config = Config.get_instance()
        if config.auth_username and config.auth_password:
            async with get_session() as session:
                count = int((await session.execute(text("SELECT COUNT(*) FROM users"))).scalar_one())
                if count:
                    return
                hashed: str = await password_hash(config.auth_password)
                await session.execute(
                    text(
                        "INSERT INTO users (username, password_hash) "
                        "SELECT :username, :password_hash WHERE NOT EXISTS (SELECT 1 FROM users)"
                    ),
                    {"username": config.auth_username, "password_hash": hashed},
                )
                await session.commit()

    def create_ws_ticket(self, user: dict) -> str:
        ticket = f"ytp_ws_{secrets.token_urlsafe(32)}"
        cache = Cache.get_instance()
        cache.set(cache.hash(ticket), {"id": user["id"], "username": user["username"]}, ttl=WS_TICKET_TTL)
        return ticket

    def consume_ws_ticket(self, ticket: str) -> dict | None:
        if not ticket or not ticket.startswith("ytp_ws_"):
            return None
        cache = Cache.get_instance()
        key = cache.hash(ticket)
        user = cache.get(key)
        if user is None:
            return None
        cache.delete(key)
        return user if isinstance(user, dict) else None

    async def user_count(self) -> int:
        async with get_session() as session:
            return int((await session.execute(text("SELECT COUNT(*) FROM users"))).scalar_one())

    async def get_user(self, user_id: int) -> dict | None:
        async with get_session() as session:
            row = (
                (await session.execute(text("SELECT id, username FROM users WHERE id = :id"), {"id": user_id}))
                .mappings()
                .first()
            )
            return dict(row) if row else None

    async def authenticate_password(self, username: str, password: str) -> dict | None:
        async with get_session() as session:
            row = (
                (
                    await session.execute(
                        text("SELECT id, username, password_hash FROM users WHERE username = :username"),
                        {"username": username},
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            return None
        if not await password_matches(password, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"]}

    def attempt_allowed(self, remote: str | None) -> bool:
        cache: Cache = Cache.get_instance()
        key: str = cache.hash(f"auth:attempt:{remote or 'unknown'}")
        attempts = cache.get(key, 0)
        count: int = attempts if isinstance(attempts, int) else 0
        if count >= LOGIN_ATTEMPTS:
            return False
        cache.set(key, count + 1, ttl=LOGIN_WINDOW)
        return True

    def clear_attempts(self, remote: str | None) -> None:
        cache = Cache.get_instance()
        cache.delete(cache.hash(f"auth:attempt:{remote or 'unknown'}"))

    async def create_session(self, user_id: int) -> str:
        token: str = secrets.token_urlsafe(32)
        expires: str = (datetime.now(UTC) + timedelta(days=SESSION_DAYS)).strftime("%Y-%m-%d %H:%M:%S.%f")
        async with get_session() as session:
            await session.execute(
                text("INSERT INTO sessions (token_digest, user_id, expires_at) VALUES (:digest, :user_id, :expires)"),
                {"digest": _digest(token), "user_id": user_id, "expires": expires},
            )
            await session.commit()
        return token

    async def session_user(self, token: str) -> dict | None:
        async with get_session() as session:
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id "
                            "WHERE sessions.token_digest = :digest AND sessions.expires_at > CURRENT_TIMESTAMP"
                        ),
                        {"digest": _digest(token)},
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    async def revoke_session(self, token: str) -> None:
        async with get_session() as session:
            await session.execute(text("DELETE FROM sessions WHERE token_digest = :digest"), {"digest": _digest(token)})
            await session.commit()

    async def user_from_key(self, key: str) -> dict | None:
        if not key.startswith("ytp_"):
            return None
        async with get_session() as session:
            row = (
                (
                    await session.execute(
                        text(
                            "SELECT users.id, users.username, api_keys.id AS key_id FROM api_keys "
                            "JOIN users ON users.id = api_keys.user_id WHERE api_keys.key_digest = :digest"
                        ),
                        {"digest": _digest(key)},
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            await session.execute(
                text("UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = :id"), {"id": row["key_id"]}
            )
            await session.commit()
            return {"id": row["id"], "username": row["username"]}

    async def create_user(self, username: str, password: str) -> dict | None:
        hashed: str = await password_hash(password)
        async with get_session() as session:
            try:
                result = await session.execute(
                    text(
                        "INSERT INTO users (username, password_hash) "
                        "SELECT :username, :password_hash WHERE NOT EXISTS (SELECT 1 FROM users) RETURNING id, username"
                    ),
                    {"username": username, "password_hash": hashed},
                )
                row = result.mappings().first()
                await session.commit()
                return dict(row) if row else None
            except IntegrityError:
                await session.rollback()
                return None

    async def update_user(self, user_id: int, username: str | None, password: str | None) -> dict:
        values = {"id": user_id, "username": username}
        async with get_session() as session:
            try:
                if username is not None:
                    await session.execute(
                        text("UPDATE users SET username = :username, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                        values,
                    )
                if password is not None:
                    await session.execute(
                        text(
                            "UPDATE users SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP WHERE id = :id"
                        ),
                        {"id": user_id, "password_hash": await password_hash(password)},
                    )
                    await session.execute(text("DELETE FROM sessions WHERE user_id = :id"), {"id": user_id})
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                msg = "Username already exists."
                raise ValueError(msg) from exc
        updated = await self.get_user(user_id)
        if updated is None:
            msg = "User was not found after update."
            raise RuntimeError(msg)
        return updated

    async def keys(self, user_id: int) -> list[dict]:
        async with get_session() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT id, name, hint, created_at, last_used_at FROM api_keys "
                            "WHERE user_id = :user_id ORDER BY created_at DESC"
                        ),
                        {"user_id": user_id},
                    )
                )
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]

    async def create_key(self, user_id: int, name: str) -> tuple[dict, str]:
        key = f"ytp_{secrets.token_urlsafe(32)}"
        async with get_session() as session:
            row = (
                (
                    await session.execute(
                        text(
                            "INSERT INTO api_keys (user_id, name, key_digest, hint) "
                            "VALUES (:user_id, :name, :digest, :hint) RETURNING id, name, hint, created_at, last_used_at"
                        ),
                        {"user_id": user_id, "name": name, "digest": _digest(key), "hint": key[-8:]},
                    )
                )
                .mappings()
                .one()
            )
            await session.commit()
        return dict(row), key

    async def delete_key(self, user_id: int, key_id: int) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text("DELETE FROM api_keys WHERE id = :id AND user_id = :user_id"), {"id": key_id, "user_id": user_id}
            )
            await session.commit()
            return bool(getattr(result, "rowcount", 0))
