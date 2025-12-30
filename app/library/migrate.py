# flake8: noqa: S608
"""
This module is a fork of the Caribou library
(https://pypi.org/project/caribou/) modified to work for our specific use case.
"""

import contextlib
import datetime
import glob
import os.path
import traceback
from collections.abc import AsyncIterator, Iterable, Sequence
from importlib.machinery import ModuleSpec, SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from types import ModuleType

UTC_LENGTH = 14

__version__ = "1.0.0"


class Error(Exception):
    """Base class for all Caribou errors."""


class InvalidMigrationError(Error):
    """Thrown when a client migration contains an error."""


class InvalidNameError(Error):
    """Thrown when a client migration has an invalid filename."""

    def __init__(self, filename: str):
        msg: str = (
            f"Migration filenames must start with a UTC timestamp. The following file has an invalid name: {filename}"
        )
        super().__init__(msg)


@contextlib.asynccontextmanager
async def execute(
    conn: aiosqlite.Connection, sql: str, params: Sequence[object] | None = None
) -> AsyncIterator[aiosqlite.Cursor]:
    params = [] if params is None else params
    cursor = await conn.execute(sql, params)
    try:
        yield cursor
    finally:
        await cursor.close()


@contextlib.asynccontextmanager
async def transaction(conn: aiosqlite.Connection) -> AsyncIterator[None]:
    try:
        yield
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


class Migration:
    """This class represents a migration version."""

    def __init__(self, path: str):
        self.path: str = path
        self.filename: str = os.path.basename(path)
        self.module_name, _ = os.path.splitext(self.filename)
        self.get_version()  # will assert the filename is valid
        self.name: str = self.module_name[UTC_LENGTH:]
        while self.name.startswith("_"):
            self.name: str = self.name[1:]

        loader = SourceFileLoader(self.module_name, path)
        spec: ModuleSpec | None = spec_from_loader(self.module_name, loader)
        if spec is None:
            msg = f"Cannot create spec for {path}"
            raise ImportError(msg)

        try:
            module: ModuleType = module_from_spec(spec)
            loader.exec_module(module)
            self.module: ModuleType = module
        except Exception as e:
            msg: str = f"Invalid migration {path}: {traceback.format_exc()}"
            raise InvalidMigrationError(msg) from e

        targets: list[str] = ["upgrade", "downgrade"]
        missing: list[str] = [m for m in targets if not self.has_method(m)]
        if missing:
            msg = f"Migration '{self.path}' is missing required methods: {', '.join(missing)}."
            raise InvalidMigrationError(msg)

    def get_version(self) -> str:
        if len(self.filename) < UTC_LENGTH:
            raise InvalidNameError(self.filename)
        timestamp: str = self.filename[:UTC_LENGTH]
        if not timestamp.isdigit():
            raise InvalidNameError(self.filename)
        return timestamp

    async def upgrade(self, conn: aiosqlite.Connection) -> None:
        await self.module.upgrade(conn)

    async def downgrade(self, conn: aiosqlite.Connection) -> None:
        await self.module.downgrade(conn)

    def has_method(self, name: str) -> bool:
        return callable(getattr(self.module, name, None))

    def __repr__(self) -> str:
        return f"Migration(path={self.filename})"


class Database:
    def __init__(self, db_url: aiosqlite.Connection | str, version_table: str = "migration_version"):
        if not db_url:
            msg = "Database requires db_url."
            raise ValueError(msg)

        self.version_table: str = version_table

        self._owns_connection = bool(isinstance(db_url, str))
        if self._owns_connection:
            self.conn: aiosqlite.Connection | None = None
            self.db_url: str = db_url
            self._ensure_connection()
        else:
            self.conn: aiosqlite.Connection = db_url

    async def __aenter__(self) -> "Database":
        if self._owns_connection:
            await self._ensure_connection()

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if not self._owns_connection:
            return
        await self.close()

    async def close(self) -> None:
        if self._owns_connection and self.conn:
            await self.conn.close()
            self.conn = None

    async def _ensure_connection(self) -> None:
        if self.conn:
            return
        self.conn = await aiosqlite.connect(self.db_url)
        self.conn.row_factory = aiosqlite.Row

    async def is_version_controlled(self) -> bool:
        await self._ensure_connection()
        assert self.conn
        sql = """SELECT * FROM sqlite_master WHERE type = 'table' AND name = ?"""
        async with execute(self.conn, sql, [self.version_table]) as cursor:
            return bool(await cursor.fetchall())

    async def upgrade(self, migrations: list[Migration], target_version: str | None = None) -> None:
        await self._ensure_connection()
        assert self.conn
        if target_version:
            _assert_migration_exists(migrations, target_version)

        migrations.sort(key=lambda x: x.get_version())
        database_version = await self.get_version()

        for migration in migrations:
            current_version: str = migration.get_version()
            if database_version is not None and current_version <= database_version:
                continue
            if target_version and current_version > target_version:
                break
            await migration.upgrade(self.conn)
            new_version: str = migration.get_version()
            await self.update_version(new_version)
            database_version: str = new_version

    async def downgrade(self, migrations: list[Migration], target_version: str | int) -> None:
        await self._ensure_connection()
        assert self.conn
        if target_version not in (0, "0"):
            _assert_migration_exists(migrations, target_version)

        migrations.sort(key=lambda x: x.get_version(), reverse=True)
        database_version: str | None = await self.get_version()

        for i, migration in enumerate(migrations):
            current_version: str = migration.get_version()
            if database_version is not None and current_version > database_version:
                continue
            if current_version <= target_version:
                break
            await migration.downgrade(self.conn)
            next_version: str | int = 0
            if i < len(migrations) - 1:
                next_migration: Migration = migrations[i + 1]
                next_version = next_migration.get_version()
            await self.update_version(str(next_version))
            database_version = str(next_version)

    async def get_version(self) -> str | None:
        """
        Return the database's version, or None if it is not under version
        control.
        """
        await self._ensure_connection()
        assert self.conn
        if not await self.is_version_controlled():
            return None
        sql: str = f"SELECT version FROM {self.version_table}"
        async with execute(self.conn, sql) as cursor:
            result = await cursor.fetchall()
            return result[0][0] if result else "0"

    async def update_version(self, version: str) -> None:
        await self._ensure_connection()
        assert self.conn
        sql: str = f"UPDATE {self.version_table} SET version = ?"
        async with transaction(self.conn):
            await self.conn.execute(sql, [version])

    async def initialize_version_control(self) -> None:
        await self._ensure_connection()
        assert self.conn
        sql: str = f"""CREATE TABLE IF NOT EXISTS {self.version_table} ( version TEXT ) """
        async with transaction(self.conn):
            await self.conn.execute(sql)
            await self.conn.execute(f"INSERT INTO {self.version_table} VALUES (0)")

    def __repr__(self) -> str:
        return f'Database("{self.db_url if self._owns_connection else "external_connection"}")'


def _assert_migration_exists(migrations: Iterable[Migration], version: str | int) -> None:
    if version not in (m.get_version() for m in migrations):
        msg: str = f"No migration with version {version} exists."
        raise Error(msg)


def load_migrations(directory: str) -> list[Migration]:
    """Return the migrations contained in the given directory."""
    directory = str(directory)
    if not os.path.exists(directory) or not os.path.isdir(directory):
        msg: str = f"{directory} is not a directory."
        raise Error(msg)
    return [Migration(f) for f in glob.glob(os.path.join(directory, "*.py"))]


async def upgrade(db_url: aiosqlite.Connection | str, migration_dir: str, version: str | None = None) -> None:
    """
    Upgrade the given database with the migrations contained in the
    migrations directory. If a version is not specified, upgrade
    to the most recent version.
    """
    async with Database(db_url) as db:
        if not await db.is_version_controlled():
            await db.initialize_version_control()

        await db.upgrade(load_migrations(migration_dir), version)


async def downgrade(db_url: str | aiosqlite.Connection, migration_dir: str, version: str) -> None:
    """
    Downgrade the database to the given version with the migrations
    contained in the given migration directory.
    """
    async with Database(db_url) as db:
        if not await db.is_version_controlled():
            msg = f"The database {db_url} is not version controlled."
            raise Error(msg)
        migrations = load_migrations(migration_dir)
        await db.downgrade(migrations, version)


async def get_version(db_url: aiosqlite.Connection | str) -> str | None:
    """Return the migration version of the given database."""
    async with Database(db_url) as db:
        return await db.get_version()


def create_migration(name: str, directory: str | None = None) -> str:
    """
    Create a migration with the given name. If no directory is specified,
    the current working directory will be used.
    """
    directory = directory if directory else "."
    if not os.path.exists(directory) or not os.path.isdir(directory):
        msg: str = f"{directory} is not a directory."
        raise Error(msg)

    now: datetime.datetime = datetime.datetime.now(tz=datetime.UTC)
    version: str = now.strftime("%Y%m%d%H%M%S")

    contents: str = MIGRATION_TEMPLATE % {"name": name, "version": version}

    sanitized: str = name.replace(" ", "_")
    filename: str = f"{version}_{sanitized}.py"
    path: str = os.path.join(directory, filename)
    with open(path, "w") as migration_file:
        migration_file.write(contents)

    return path


MIGRATION_TEMPLATE = """\
\"\"\"
This module contains a db migration.

Migration Name: %(name)s
Migration Version: %(version)s
\"\"\"

async def upgrade(c):
    # add your upgrade step here
    await c.execute("SELECT 1")

async def downgrade(c):
    # add your downgrade step here
    await c.execute("SELECT 1")
"""
