from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from getpass import getpass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from app.features.auth.service import AuthService
from app.library.config import Config
from app.library.sqlite_store import SqliteStore


async def reset(username: str) -> None:
    previous_logging_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        config = Config.get_instance()
        db_file = Path(config.db_file)
        if not db_file.is_file():
            msg = f"Database file does not exist or is not a regular file: {db_file}"
            raise ValueError(msg)
        sys.stdout.write(f"Database: {db_file.resolve()}\n")
        sys.stdout.flush()
        store = SqliteStore.get_instance(db_path=config.db_file)
        await store.get_connection()
        try:
            auth = AuthService.get_instance()
            if await auth.find_user(username) is None:
                msg = "Account not found."
                raise ValueError(msg)
            await auth.reset_password(username, _confirmed_password())
        finally:
            await store.close()
    finally:
        logging.disable(previous_logging_level)


def _confirmed_password() -> str:
    password = getpass("New password: ")
    confirmation = getpass("Confirm new password: ")
    if password != confirmation:
        msg = "Passwords do not match."
        raise ValueError(msg)
    return password


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset the password for a YTPTube account.")
    parser.add_argument("--username", required=True, help="Username of the account to reset")
    args = parser.parse_args(argv)
    try:
        asyncio.run(reset(args.username))
    except (OSError, RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    sys.stdout.write("Password reset successfully.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
