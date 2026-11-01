import asyncio
import sqlite3
from contextlib import closing
from unittest.mock import Mock

import pytest

from app import main
from app.library.sqlite_store import SqliteStore


def test_accepts_process_arg(monkeypatch):
    start = Mock()
    monkeypatch.setattr(main, "start", start)

    main.main(["--ytp-process"])

    start.assert_called_once_with(no_auto_migration=False)


def test_migration_flag(monkeypatch):
    server = Mock()
    monkeypatch.setattr(main, "Main", server)

    main.main(["--no-auto-migration"])

    server.assert_called_once_with(no_auto_migration=True)
    server.return_value.start.assert_called_once_with()


def test_dev_migration_flag(monkeypatch):
    import watchfiles

    server = Mock()
    monkeypatch.setattr(main, "Main", server)

    def run_process(*paths, target, kwargs, **options):
        target(**kwargs)
        target(**kwargs)

    monkeypatch.setattr(watchfiles, "run_process", run_process)

    main.main(["--dev", "--no-auto-migration"])

    assert server.call_count == 2
    server.assert_called_with(no_auto_migration=True)
    assert server.return_value.start.call_count == 2


def test_revision_blocks_startup(monkeypatch, tmp_path):
    db_path = tmp_path / "database.db"
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("CREATE TABLE migration_version (version TEXT)")
        db.execute("INSERT INTO migration_version VALUES ('20000101000000')")
    SqliteStore._reset_singleton()
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(main.asyncio, "get_event_loop", lambda: loop)
    worker = Mock()
    events = Mock()
    serve = Mock()
    monkeypatch.setattr(main, "BackgroundWorker", worker)
    monkeypatch.setattr(main, "EventBus", events)
    monkeypatch.setattr(main.web, "run_app", serve)
    server = object.__new__(main.Main)
    server._no_auto_migration = True
    server._config = Mock(spec=main.Config, db_file=str(db_path), host="localhost", port=8081)

    try:
        with pytest.raises(RuntimeError, match="Start without --no-auto-migration"):
            server.start()

        worker.get_instance.assert_not_called()
        events.get_instance.assert_not_called()
        serve.assert_not_called()
    finally:
        loop.run_until_complete(asyncio.wait_for(SqliteStore.get_instance().close(), timeout=5))
        loop.close()
        SqliteStore._reset_singleton()
