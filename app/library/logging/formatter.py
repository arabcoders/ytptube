from __future__ import annotations

import json
import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_RECORD_ATTRS: set[str] = set(logging.makeLogRecord({}).__dict__) | {"asctime", "message"}
SKIP_LOG_FIELD = object()


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        source = {
            "path": record.pathname,
            "file": record.filename,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "datetime": self.formatTime(record),
            "level": record.levelname.lower(),
            "levelno": record.levelno,
            "logger": record.name,
            "message": record.getMessage(),
            "source": source,
            "process": {"id": record.process, "name": record.processName},
            "thread": {"id": record.thread, "name": record.threadName},
            "fields": self._extra(record),
        }

        if record.exc_info:
            exception = self._exception(record.exc_info)
            if exception is not None:
                data["exception"] = exception
                data["source"].update(self._exception_source(exception))

        return json.dumps(data, ensure_ascii=False, default=str)

    def formatTime(self, record, datefmt=None):  # noqa: N802
        _ = datefmt
        return datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="milliseconds")

    @staticmethod
    def _extra(record: logging.LogRecord) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in LOG_RECORD_ATTRS or key.startswith("_"):
                continue

            value = JsonLogFormatter._field(value)
            if value is not SKIP_LOG_FIELD:
                extra[key] = value

        return extra

    @staticmethod
    def _field(value: Any) -> Any:
        if isinstance(value, str | int | float | bool) or value is None:
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            data: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str) or key.startswith("_"):
                    continue
                item = JsonLogFormatter._field(item)
                if item is not SKIP_LOG_FIELD:
                    data[key] = item
            return data
        if isinstance(value, list | tuple | set):
            data: list[Any] = []
            for item in value:
                item = JsonLogFormatter._field(item)
                if item is not SKIP_LOG_FIELD:
                    data.append(item)
            return data
        try:
            return str(value)
        except Exception:
            return SKIP_LOG_FIELD

    @staticmethod
    def _exception(
        exc_info: tuple[type[BaseException], BaseException, Any] | tuple[None, None, None],
    ) -> dict[str, Any] | None:
        exc = exc_info[1]
        if exc is None:
            return None
        stack = JsonLogFormatter._exception_stack(exc_info)
        data: dict[str, Any] = {"type": JsonLogFormatter._exception_type(exc)}
        message = str(exc).strip()
        if message:
            data["message"] = message
        if stack:
            origin = stack[-1]
            data["file"] = origin["path"]
            data["line"] = origin["line"]
            data["stack"] = stack
        return data

    @staticmethod
    def _exception_type(exc: BaseException) -> str:
        module = exc.__class__.__module__
        name = exc.__class__.__qualname__
        return name if module == "builtins" else f"{module}.{name}"

    @staticmethod
    def _exception_stack(
        exc_info: tuple[type[BaseException], BaseException, Any] | tuple[None, None, None],
    ) -> list[dict[str, Any]]:
        exc = exc_info[1]
        tb = exc_info[2] if len(exc_info) > 2 else None
        if tb is None and exc is not None:
            tb = exc.__traceback__
        if tb is None:
            return []
        return [JsonLogFormatter._frame(frame) for frame in traceback.extract_tb(tb)]

    @staticmethod
    def _frame(frame: traceback.FrameSummary) -> dict[str, Any]:
        file_path = Path(frame.filename)
        return {
            "path": frame.filename,
            "file": file_path.name,
            "module": file_path.stem,
            "function": frame.name,
            "line": frame.lineno,
        }

    @staticmethod
    def _exception_source(exception: dict[str, Any]) -> dict[str, Any]:
        source: dict[str, Any] = {}
        path = exception.get("file")
        if isinstance(path, str) and path:
            file_path = Path(path)
            source.update({"path": path, "file": file_path.name, "module": file_path.stem})
        line = exception.get("line")
        if isinstance(line, int):
            source["line"] = line
        stack = exception.get("stack")
        if isinstance(stack, list) and stack and isinstance(stack[-1], dict):
            frame = stack[-1]
            for key in ("function", "module"):
                value = frame.get(key)
                if isinstance(value, str) and value:
                    source[key] = value
        return source
