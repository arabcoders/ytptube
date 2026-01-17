#!/usr/bin/env python3
"""
Caribou migrations CLI.

Provides commands to create, list, and apply database migrations.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

APP_ROOT: Path = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.library import migrate

if TYPE_CHECKING:
    from collections.abc import Callable


def e_print(msg: str = "") -> None:
    sys.stderr.write(f"{msg}\n")


def o_print(msg: str = "") -> None:
    sys.stdout.write(f"{msg}\n")


def cmd_info(_: argparse.Namespace) -> None:
    o_print(f"Version: {migrate.__version__}")


def cmd_create(args: argparse.Namespace) -> None:
    path = migrate.create_migration(args.name, args.migration_dir)
    o_print(f"created migration {path}")


async def cmd_version(args: argparse.Namespace) -> None:
    version = await migrate.get_version(args.database_path)
    if version:
        o_print(f"the db [{args.database_path}] is at version {version}")
    else:
        o_print(f"the db [{args.database_path}] is not under version control")


async def cmd_upgrade(args: argparse.Namespace) -> None:
    if args.version:
        o_print(f"upgrading db [{args.database_path}] to version [{args.version}]")
    else:
        o_print(f"upgrading db [{args.database_path}] to most recent version")

    await migrate.upgrade(args.database_path, args.migration_dir, args.version)

    new_version = await migrate.get_version(args.database_path)
    if args.version is not None:
        assert new_version == args.version

    o_print(f"upgraded [{args.database_path}] successfully to version [{new_version}]")


async def cmd_downgrade(args: argparse.Namespace) -> None:
    o_print(f"downgrading db [{args.database_path}] to version [{args.version}]")
    await migrate.downgrade(args.database_path, args.migration_dir, args.version)
    o_print(f"downgraded [{args.database_path}] successfully to version [{args.version}]")


def cmd_list(args: argparse.Namespace) -> None:
    o_print(f"Migrations in [{args.migration_dir}]:\n")
    for m in migrate.load_migrations(args.migration_dir):
        o_print(f"{m.get_version()}\t{m.name}\t{m.path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="caribou")
    sub = p.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="print library version")
    info.set_defaults(func=cmd_info)

    create = sub.add_parser("create", help="create a new migration file")
    create.add_argument("name", help="the name of migration")
    create.add_argument("-d", "--migration-dir", default=".", help="the migration directory")
    create.set_defaults(func=cmd_create)

    ver = sub.add_parser("version", help="return the migration version of the database")
    ver.add_argument("database_path", help="path to the sqlite database")
    ver.set_defaults(func=cmd_version)

    up = sub.add_parser(
        "upgrade",
        help="upgrade the db (if version isn't specified, upgrade to the most recent)",
    )
    up.add_argument("database_path", help="path to the sqlite database")
    up.add_argument("migration_dir", help="the migration directory")
    up.add_argument("-v", "--version", type=int, default=None, help="the target migration version")
    up.set_defaults(func=cmd_upgrade)

    down = sub.add_parser(
        "downgrade",
        help="downgrade the db to a particular version (use 0 to rollback all changes)",
    )
    down.add_argument("database_path", help="path to the sqlite database")
    down.add_argument("migration_dir", help="the migration directory")
    down.add_argument("version", type=int, help="the target migration version")
    down.set_defaults(func=cmd_downgrade)

    lst = sub.add_parser("list", help="list the migration versions")
    lst.add_argument("migration_dir", help="the migration directory")
    lst.set_defaults(func=cmd_list)

    return p


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        func: Callable[[argparse.Namespace], None] = args.func
        # Check if function is async
        if asyncio.iscoroutinefunction(func):
            asyncio.run(func(args))
        else:
            func(args)
        return 0

    except migrate.InvalidMigrationError:
        e_print(traceback.format_exc())
        return 1

    except migrate.Error as err:
        e_print(f"Error: {err}")
        return 1

    except Exception:
        e_print("an unexpected error occurred:")
        e_print(traceback.format_exc())
        return 1


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
