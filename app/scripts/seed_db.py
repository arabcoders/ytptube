#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
import uuid
from datetime import UTC, datetime
from email.utils import formatdate
from itertools import cycle, islice
from pathlib import Path
from typing import TYPE_CHECKING

APP_ROOT = str((Path(__file__).parent / ".." / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app.library.DataStore import StoreType
from app.library.encoder import Encoder

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

LOG = logging.getLogger("seed_db")

USED_IDS: set[str] = set()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed history/queue with synthetic records for performance testing.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/storage/media/youtube"),
        help="Root folder to scan for media files",
    )
    parser.add_argument("--count", type=int, default=10_000, help="Total records to insert (default: 10000).")
    parser.add_argument("--batch", type=int, default=500, help="Insert batch size (default: 500).")
    parser.add_argument(
        "--store",
        choices=[StoreType.HISTORY.value, StoreType.QUEUE.value],
        default=StoreType.HISTORY.value,
        help="Target store type (done|queue). Default: done.",
    )
    parser.add_argument(
        "--extension",
        default=".mkv",
        help="File extension to look for (default: .mkv).",
    )
    parser.add_argument(
        "--status",
        default="finished",
        help="Status value to set on seeded items (default: finished).",
    )
    parser.add_argument("--preset", default="default", help="Preset to stamp on items (default: default).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and plan only; do not write to the database.",
    )
    parser.add_argument("db_file", type=Path, help="Path to the database file.")
    return parser.parse_args()


def connect_db(db_file: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database=db_file, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=wal")
    return conn


def find_files(root: Path, extension: str) -> list[Path]:
    if not root.exists():
        msg = f"Root path does not exist: {root}"
        raise FileNotFoundError(msg)

    files = [p for p in root.rglob(f"*.{extension}") if p.is_file()]
    if not files:
        msg = f"No .{extension} files found under {root!s}"
        raise FileNotFoundError(msg)

    return files


def _cycle(files: Sequence[Path]) -> Iterator[Path]:
    return cycle(files)


def _relative_folder(path: Path, root: Path) -> tuple[str, str]:
    try:
        rel = path.relative_to(root)
        folder = "" if rel.parent == Path(".") else rel.parent.as_posix()
        filename = rel.name
    except ValueError:
        folder = ""
        filename = path.name

    return folder, filename


def _build_row(
    path: Path,
    root: Path,
    idx: int,
    status: str,
    preset: str,
    store: StoreType,
) -> tuple[str, str, str, str, str]:
    folder, filename = _relative_folder(path, root)
    stat = path.stat()

    video_id = re.search(r"\[youtube-(\S+)\]", path.stem)
    video_id = f"seeded_video_{idx:06d}" if not video_id else video_id.group(1)
    if video_id in USED_IDS:
        video_id = f"{video_id}_{uuid.uuid4().hex[:6]}"
    USED_IDS.add(video_id)

    archive_id = f"youtube {video_id}"
    record_id = f"seed-{idx:06d}-{uuid.uuid4().hex[:12]}"
    timestamp = datetime.now(UTC)

    data = {
        "_id": record_id,
        "id": video_id,
        "title": path.stem,
        "description": "",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "preset": preset,
        "folder": folder,
        "download_dir": str(root),
        "temp_dir": None,
        "status": status,
        "cookies": None,
        "template": None,
        "template_chapter": None,
        "timestamp": time.time_ns(),
        "is_live": False,
        "datetime": formatdate(timestamp.timestamp()),
        "live_in": None,
        "file_size": stat.st_size,
        "options": {},
        "extras": {
            "source_name": "Tester",
            "source_id": "0ddc40f3-9227-4ffa-9f3c-c52bcf33ef2f",
            "source_handler": "YoutubeHandler",
            "metadata": {
                "published": formatdate(timestamp.timestamp()),
            },
            "is_video": True,
            "is_audio": True,
        },
        "cli": "",
        "auto_start": True,
        "is_archivable": True,
        "is_archived": True,
        "archive_id": archive_id,
        "tmpfilename": None,
        "filename": filename,
        "total_bytes": stat.st_size,
        "total_bytes_estimate": stat.st_size,
        "downloaded_bytes": stat.st_size,
        "msg": None,
        "percent": 100,
        "speed": None,
        "eta": None,
    }

    created_at = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    encoded = Encoder(sort_keys=True, indent=4).encode(data)

    return (record_id, str(store), data["url"], encoded, created_at)


def generate_rows(
    files: Sequence[Path],
    root: Path,
    total: int,
    status: str,
    preset: str,
    store: StoreType,
) -> Iterable[tuple[str, str, str, str, str]]:
    _iter = _cycle(files)
    for idx, path in enumerate(islice(_iter, total)):
        yield _build_row(path, root, idx, status, preset, store)


def insert_batches(
    conn: sqlite3.Connection,
    rows: Iterable[tuple[str, str, str, str, str]],
    batch_size: int,
) -> int:
    sql = """
    INSERT INTO "history" ("id", "type", "url", "data", "created_at")
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT("id") DO UPDATE SET
        "type" = excluded.type,
        "url" = excluded.url,
        "data" = excluded.data,
        "created_at" = excluded.created_at
    """
    total_written = 0
    batch: list[tuple[str, str, str, str, str]] = []

    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            conn.executemany(sql, batch)
            total_written += len(batch)
            LOG.info("Inserted %d rows...", total_written)
            batch.clear()

    if batch:
        conn.executemany(sql, batch)
        total_written += len(batch)

    return total_written


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    extension = args.extension.lstrip(".")
    store = StoreType.from_value(args.store)

    files = find_files(args.root, extension)
    LOG.info("Found %d %s files under %s", len(files), extension, args.root)

    if args.dry_run:
        LOG.info("Dry run only. Would insert %d rows into '%s'.", args.count, store.value)
        return

    rows = generate_rows(files, args.root, args.count, args.status, args.preset, store)
    conn = connect_db(args.db_file)
    try:
        written = insert_batches(conn, rows, args.batch)
    finally:
        conn.close()

    LOG.info("Done. Inserted %d rows into '%s'.", written, store.value)


if __name__ == "__main__":
    main()
