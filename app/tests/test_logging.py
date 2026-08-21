import asyncio
import json
import logging
import sys
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from app.library.logging import (
    JsonLogFormatter,
    get_logger,
    read_logfile,
    set_runtime_log_level,
    setup_logging,
    tail_log,
)


@pytest.fixture
def logging_state():
    root = logging.getLogger()
    app_logger = get_logger()
    handlers = list(root.handlers)
    handler_state = {handler: (handler.level, handler.formatter) for handler in handlers}
    root_level = root.level
    app_level = app_logger.level
    for handler in handlers:
        if getattr(handler, "ytptube_managed_json", False):
            root.removeHandler(handler)
    yield
    for handler in list(root.handlers):
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    for handler, (level, formatter) in handler_state.items():
        if handler not in root.handlers:
            root.addHandler(handler)
        handler.setLevel(level)
        handler.setFormatter(formatter)
    root.setLevel(root_level)
    app_logger.setLevel(app_level)


def test_formatter_schema():
    record = logging.LogRecord("test.logger", logging.WARNING, __file__, 123, "hello %s", ("world",), None)
    record.download_id = "abc"
    record.payload = {
        "enabled": True,
        "items": [{"name": "one", "path": Path("downloads/file.mp4")}],
        "_token": "secret",
    }
    record.tags = ["video", {"quality": "720p", "_private": "hidden"}]
    record.ytdlp_opts = {
        "paths": {"home": Path("downloads"), "temp": Path("tmp")},
        "progress_hooks": [lambda _: None],
        "postprocessors": ({"key": "FFmpegMetadata"},),
    }
    record._private = "hidden"
    data = json.loads(JsonLogFormatter().format(record))

    assert uuid.UUID(data["id"])
    assert data["level"] == "warning"
    assert data["levelno"] == logging.WARNING
    assert data["logger"] == "test.logger"
    assert data["message"] == "hello world"
    assert data["fields"] == {
        "download_id": "abc",
        "payload": {"enabled": True, "items": [{"name": "one", "path": "downloads/file.mp4"}]},
        "tags": ["video", {"quality": "720p"}],
        "ytdlp_opts": {
            "paths": {"home": "downloads", "temp": "tmp"},
            "progress_hooks": [data["fields"]["ytdlp_opts"]["progress_hooks"][0]],
            "postprocessors": [{"key": "FFmpegMetadata"}],
        },
    }
    assert "<lambda>" in data["fields"]["ytdlp_opts"]["progress_hooks"][0]
    assert data["source"]["line"] == 123


def test_formatter_exception():
    try:
        raise ValueError("bad")
    except ValueError:
        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    data = json.loads(JsonLogFormatter().format(record))

    assert data["message"] == "failed"
    assert data["exception"]["type"] == "ValueError"
    assert data["exception"]["message"] == "bad"
    assert data["exception"]["file"] == __file__
    assert data["exception"]["line"] > 0
    assert data["source"] == data["exception"]["stack"][-1]
    assert data["exception"]["stack"][-1]["function"] == "test_formatter_exception"
    assert "exception_message" not in data


def test_formatter_no_stack():
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failed", (), None)
    record.stack_info = 'Stack (most recent call last):\n  File "x", line 1, in y'
    data = json.loads(JsonLogFormatter().format(record))
    assert "stack" not in data


@pytest.mark.asyncio
async def test_read_missing(tmp_path):
    result = await read_logfile(tmp_path / "missing.log")
    assert result == {"logs": [], "next_offset": None, "end_is_reached": True}


@pytest.mark.asyncio
async def test_read_records(tmp_path):
    file = tmp_path / "app.jsonl"
    entries = [
        {"id": "log-1", "datetime": "now", "level": "info", "logger": "test", "message": "line 1"},
        {"id": "log-2", "datetime": "now", "level": "warning", "logger": "test", "message": "line 2"},
        {
            "id": "log-3",
            "datetime": "now",
            "level": "error",
            "logger": "test",
            "message": "line 3",
            "exception": {"type": "ValueError", "message": "bad"},
        },
    ]
    file.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
    result = await read_logfile(file, limit=2)
    assert [entry["id"] for entry in result["logs"]] == ["log-2", "log-3"]
    assert [entry["message"] for entry in result["logs"]] == ["line 2", "line 3"]
    assert result["logs"][1]["exception"]["type"] == "ValueError"
    assert result["next_offset"] == 2
    assert result["end_is_reached"] is False


@pytest.mark.asyncio
async def test_read_invalid(tmp_path):
    file = tmp_path / "app.jsonl"
    file.write_text("not-json\n" + json.dumps({"message": "ignored"}) + "\n")
    result = await read_logfile(file, limit=1)
    assert result["logs"] == []


@pytest.mark.asyncio
async def test_tail_missing(tmp_path):
    async def emit(_: dict) -> None:
        pass

    await tail_log(tmp_path / "missing.log", emit)


@pytest.mark.asyncio
async def test_tail_records(tmp_path):
    file = tmp_path / "app.jsonl"
    file.write_text("")
    emitted: list[dict] = []

    async def emit(entry: dict) -> None:
        emitted.append(entry)
        raise asyncio.CancelledError

    task = asyncio.create_task(tail_log(file, emit, sleep_time=0.01))
    await asyncio.sleep(0.02)
    file.write_text(
        json.dumps({"id": "tail-1", "datetime": "now", "level": "info", "logger": "tail", "message": "live"}) + "\n"
    )
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    assert emitted[0]["message"] == "live"
    assert emitted[0]["id"] == "tail-1"


def test_setup_levels(tmp_path, logging_state):
    setup_logging("critical", tmp_path / "app.jsonl")
    handler = next(
        handler for handler in logging.getLogger().handlers if getattr(handler, "ytptube_managed_json", False)
    )
    assert handler.level == logging.CRITICAL


def test_setup_unique(tmp_path, logging_state):
    root = logging.getLogger()
    path = tmp_path / "app.jsonl"
    setup_logging("info", path)
    original = next(handler for handler in root.handlers if getattr(handler, "ytptube_managed_json", False))
    duplicate = TimedRotatingFileHandler(path, when="midnight", backupCount=3, encoding="utf-8")
    setattr(duplicate, "ytptube_managed_json", True)
    root.addHandler(duplicate)
    setup_logging("info", path)
    managed = [handler for handler in root.handlers if getattr(handler, "ytptube_managed_json", False)]
    assert managed == [original]
    assert duplicate not in root.handlers


def test_none_disables_file(tmp_path, logging_state):
    root = logging.getLogger()
    setup_logging("info", tmp_path / "app.jsonl")
    setup_logging("info")
    assert not any(getattr(handler, "ytptube_managed_json", False) for handler in root.handlers)


def test_debug_writes_file(tmp_path, logging_state):
    root = logging.getLogger()
    app_logger = get_logger()
    app_logger.setLevel(logging.INFO)
    setup_logging("info", tmp_path / "app.jsonl")
    set_runtime_log_level("debug")
    app_logger.debug("debug record")
    managed = next(handler for handler in root.handlers if getattr(handler, "ytptube_managed_json", False))
    managed.flush()
    data = json.loads((tmp_path / "app.jsonl").read_text().splitlines()[0])
    assert data["message"] == "debug record"
