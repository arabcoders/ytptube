from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from Crypto.Protocol.KDF import bcrypt, bcrypt_check

from app.features.auth.repository import AuthRepository
from app.library.cache import Cache
from app.library.config import Config
from app.library.Services import Services
from app.library.Singleton import Singleton
from app.library.sqlite_store import SqliteStore

BCRYPT_COST = 12
WS_TICKET_TTL = 30
LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 60


def _datetime_value(value: datetime | None) -> str | None:
    return str(value.replace(tzinfo=None)) if value is not None else None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _password_hash(password: str) -> str:
    if not password or "\x00" in password or len(password.encode()) > 72:
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
    def __init__(self) -> None:
        self._repo = AuthRepository.get_instance()

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
            if await self._repo.count_users():
                return
            hashed: str = await password_hash(config.auth_password)
            await self._repo.create_user(config.auth_username, hashed, require_empty=True)

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
        return await self._repo.count_users()

    async def get_user(self, user_id: int) -> dict | None:
        user = await self._repo.get_user(user_id)
        return {"id": user.id, "username": user.username} if user else None

    async def find_user(self, username: str) -> dict | None:
        user = await self._repo.find_user(username)
        return {"id": user.id, "username": user.username} if user else None

    async def authenticate_password(self, username: str, password: str) -> dict | None:
        user = await self._repo.find_user(username)
        if not user:
            return None
        if not await password_matches(password, user.password_hash):
            return None
        return {"id": user.id, "username": user.username}

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

    async def create_session(self, user_id: int, user_agent: str | None = None, ip: str | None = None) -> str:
        token: str = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(days=Config.get_instance().auth_session_days)
        await self._repo.create_session(_digest(token), expires, user_id, user_agent, ip)
        return token

    async def session_user(self, token: str) -> dict | None:
        user = await self._repo.session_user(_digest(token))
        return {"id": user.id, "username": user.username} if user else None

    async def revoke_session(self, token: str) -> None:
        await self._repo.revoke_session(_digest(token))

    async def sessions(self, user_id: int, current_token: str | None = None) -> list[dict]:
        rows = await self._repo.sessions(user_id, _digest(current_token) if current_token else None)
        return [
            {
                "id": model.id,
                "created_at": _datetime_value(model.created_at),
                "expires_at": _datetime_value(model.expires_at),
                "user_agent": model.user_agent,
                "ip": model.ip,
                "current": current,
            }
            for model, current in rows
        ]

    async def delete_session(self, user_id: int, session_id: int) -> bool:
        return await self._repo.delete_session(user_id, session_id)

    async def revoke_other_sessions(self, user_id: int, token: str) -> None:
        await self._repo.revoke_other_sessions(user_id, _digest(token))

    async def user_from_key(self, key: str) -> dict | None:
        if not key.startswith("ytp_"):
            return None
        row = await self._repo.user_from_key(_digest(key))
        if row is None:
            return None
        user, _ = row
        return {"id": user.id, "username": user.username}

    async def create_user(self, username: str, password: str, *, require_empty: bool = False) -> dict | None:
        hashed: str = await password_hash(password)
        user = await self._repo.create_user(username, hashed, require_empty)
        return {"id": user.id, "username": user.username} if user else None

    async def update_user(self, user_id: int, username: str | None, password: str | None) -> dict:
        hashed = await password_hash(password) if password is not None else None
        await self._repo.update_user(user_id, username, hashed)
        updated = await self.get_user(user_id)
        if updated is None:
            msg = "User was not found after update."
            raise RuntimeError(msg)
        return updated

    async def reset_password(self, username: str, password: str) -> None:
        hashed = await password_hash(password)
        if not await self._repo.reset_password(username, hashed):
            msg = "Account not found."
            raise ValueError(msg)

    async def keys(self, user_id: int) -> list[dict]:
        return [
            {
                "id": model.id,
                "name": model.name,
                "hint": model.hint,
                "created_at": _datetime_value(model.created_at),
                "last_used_at": _datetime_value(model.last_used_at),
            }
            for model in await self._repo.keys(user_id)
        ]

    async def create_key(self, user_id: int, name: str) -> tuple[dict, str]:
        key = f"ytp_{secrets.token_urlsafe(32)}"
        model = await self._repo.create_key(user_id, name, _digest(key), key[-8:])
        return {
            "id": model.id,
            "name": model.name,
            "hint": model.hint,
            "created_at": _datetime_value(model.created_at),
            "last_used_at": _datetime_value(model.last_used_at),
        }, key

    async def delete_key(self, user_id: int, key_id: int) -> bool:
        return await self._repo.delete_key(user_id, key_id)
