from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, exists, func, insert, literal, select, update
from sqlalchemy.exc import IntegrityError

from app.features.auth.models import ApiKeyModel, SessionModel, UserModel
from app.features.core.deps import get_session
from app.features.core.models import utcnow
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager
    from datetime import datetime

    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession

    SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class AuthRepository(metaclass=Singleton):
    def __init__(self, session: SessionFactory | None = None) -> None:
        self.session: SessionFactory = session or get_session

    @staticmethod
    def get_instance() -> AuthRepository:
        return AuthRepository()

    async def count_users(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(UserModel))
            return int(result.scalar_one())

    async def get_user(self, user_id: int) -> UserModel | None:
        async with self.session() as session:
            return await session.get(UserModel, user_id)

    async def find_user(self, username: str) -> UserModel | None:
        async with self.session() as session:
            result = await session.execute(select(UserModel).where(UserModel.username == username).limit(1))
            return result.scalar_one_or_none()

    async def create_user(self, username: str, password_hash: str, require_empty: bool = False) -> UserModel | None:
        async with self.session() as session:
            try:
                if require_empty:
                    query = (
                        insert(UserModel)
                        .from_select(
                            [UserModel.username, UserModel.password_hash],
                            select(literal(username), literal(password_hash)).where(~exists(select(UserModel.id))),
                        )
                        .returning(UserModel)
                    )
                else:
                    query = (
                        insert(UserModel).values(username=username, password_hash=password_hash).returning(UserModel)
                    )
                result = await session.execute(query)
                model = result.scalar_one_or_none()
                await session.commit()
                return model
            except IntegrityError:
                await session.rollback()
                return None

    async def create_session(
        self, token_digest: str, expires_at: datetime, user_id: int, user_agent: str | None, ip: str | None
    ) -> None:
        async with self.session() as session:
            session.add(
                SessionModel(
                    token_digest=token_digest,
                    user_id=user_id,
                    expires_at=expires_at,
                    user_agent=user_agent,
                    ip=ip,
                )
            )
            await session.commit()

    async def session_user(self, token_digest: str) -> UserModel | None:
        async with self.session() as session:
            result = await session.execute(
                select(UserModel)
                .join(SessionModel, SessionModel.user_id == UserModel.id)
                .where(SessionModel.token_digest == token_digest, SessionModel.expires_at > utcnow())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def revoke_session(self, token_digest: str) -> None:
        async with self.session() as session:
            await session.execute(delete(SessionModel).where(SessionModel.token_digest == token_digest))
            await session.commit()

    async def sessions(self, user_id: int, token_digest: str | None) -> list[tuple[SessionModel, bool]]:
        async with self.session() as session:
            result = await session.execute(
                select(SessionModel, (SessionModel.token_digest == (token_digest or "")).label("current"))
                .where(SessionModel.user_id == user_id, SessionModel.expires_at > utcnow())
                .order_by(SessionModel.created_at.desc(), SessionModel.id.desc())
            )
            return [(row[0], bool(row[1])) for row in result.all()]

    async def delete_session(self, user_id: int, session_id: int) -> bool:
        async with self.session() as session:
            result = await session.execute(
                delete(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == user_id)
            )
            await session.commit()
            return bool(getattr(result, "rowcount", 0))

    async def revoke_other_sessions(self, user_id: int, token_digest: str) -> None:
        async with self.session() as session:
            await session.execute(
                delete(SessionModel).where(SessionModel.user_id == user_id, SessionModel.token_digest != token_digest)
            )
            await session.commit()

    async def user_from_key(self, key_digest: str) -> tuple[UserModel, ApiKeyModel] | None:
        async with self.session() as session:
            result = await session.execute(
                select(UserModel, ApiKeyModel)
                .join(ApiKeyModel, ApiKeyModel.user_id == UserModel.id)
                .where(ApiKeyModel.key_digest == key_digest)
                .limit(1)
            )
            row = result.one_or_none()
            if row is None:
                return None
            await session.execute(update(ApiKeyModel).where(ApiKeyModel.id == row[1].id).values(last_used_at=utcnow()))
            await session.commit()
            return row[0], row[1]

    async def update_user(self, user_id: int, username: str | None, password_hash: str | None) -> None:
        async with self.session() as session:
            try:
                values: dict[str, object] = {}
                if username is not None:
                    values["username"] = username
                if password_hash is not None:
                    values["password_hash"] = password_hash
                if values:
                    values["updated_at"] = utcnow()
                    await session.execute(update(UserModel).where(UserModel.id == user_id).values(values))
                if password_hash is not None:
                    await session.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                msg = "Username already exists."
                raise ValueError(msg) from exc

    async def reset_password(self, username: str, password_hash: str) -> bool:
        async with self.session() as session:
            result = await session.execute(
                update(UserModel)
                .where(UserModel.username == username)
                .values(password_hash=password_hash, updated_at=utcnow())
                .returning(UserModel.id)
            )
            user_id = result.scalar_one_or_none()
            if user_id is None:
                await session.rollback()
                return False
            await session.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
            await session.commit()
            return True

    async def keys(self, user_id: int) -> list[ApiKeyModel]:
        async with self.session() as session:
            result = await session.execute(
                select(ApiKeyModel).where(ApiKeyModel.user_id == user_id).order_by(ApiKeyModel.created_at.desc())
            )
            return list(result.scalars().all())

    async def create_key(self, user_id: int, name: str, key_digest: str, hint: str) -> ApiKeyModel:
        async with self.session() as session:
            model = ApiKeyModel(user_id=user_id, name=name, key_digest=key_digest, hint=hint)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def delete_key(self, user_id: int, key_id: int) -> bool:
        async with self.session() as session:
            result = await session.execute(
                delete(ApiKeyModel).where(ApiKeyModel.id == key_id, ApiKeyModel.user_id == user_id)
            )
            await session.commit()
            return bool(getattr(result, "rowcount", 0))
