from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.library import diagnostics


@pytest.mark.parametrize("valid", [True, False])
def test_probe_closes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid: bool) -> None:
    database = tmp_path / "database.sqlite"
    original_connect = sqlite3.connect
    if valid:
        with closing(original_connect(database)) as connection, connection:
            connection.execute("create table data (value text)")
    else:
        database.write_bytes(b"not a sqlite database")
    connections: list[sqlite3.Connection] = []

    def connect(database: str, *, timeout: float = 5, uri: bool = False) -> sqlite3.Connection:
        connection = original_connect(database, timeout=timeout, uri=uri)
        connections.append(connection)
        return connection

    monkeypatch.setattr(diagnostics.sqlite3, "connect", connect)

    try:
        status, message = diagnostics._probe_db_file(database)
        if valid:
            assert (status, message) == ("pass", "Ready.")
        else:
            assert status == "fail"
            assert message.startswith("SQLite error.")
        with pytest.raises(sqlite3.ProgrammingError):
            connections[0].execute("select 1")
    finally:
        for connection in connections:
            connection.close()
