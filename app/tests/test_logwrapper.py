import logging
from typing import Any

import pytest

from app.library.LogWrapper import LogWrapper


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def make_logger(name: str = "lw_test") -> tuple[logging.Logger, CaptureHandler]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = CaptureHandler()
    # Avoid duplicate handlers when tests run multiple times
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.addHandler(handler)
    return logger, handler


class TestLogWrapper:
    def test_add_target_type_validation(self) -> None:
        lw = LogWrapper()
        with pytest.raises(TypeError, match=r"Target must be a logging\.Logger instance or a callable"):
            lw.add_target(123)  # type: ignore[arg-type]

    def test_add_target_name_inference_and_custom(self) -> None:
        lw = LogWrapper()
        logger, _ = make_logger("one")

        # Name inferred from logger
        lw.add_target(logger)
        assert lw.targets[-1].name == "one"
        assert lw.has_targets() is True

        # Name inferred from callable
        def sink(level: int, msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            return None

        lw.add_target(sink)
        assert lw.targets[-1].name == "sink"

        # Custom name overrides
        lw.add_target(logger, name="custom")
        assert lw.targets[-1].name == "custom"

    def test_level_filtering_and_dispatch(self) -> None:
        lw = LogWrapper()
        logger, cap = make_logger("cap")
        calls: list[tuple[int, str, tuple, dict]] = []

        def sink(level: int, msg: str, *args: Any, **kwargs: Any) -> None:
            calls.append((level, msg, args, kwargs))

        # Logger target at INFO, callable target at WARNING
        lw.add_target(logger, level=logging.INFO)
        lw.add_target(sink, level=logging.WARNING)

        # DEBUG should hit none
        lw.debug("d1")
        assert len(cap.records) == 0
        assert len(calls) == 0

        # INFO hits logger only
        lw.info("hello %s", "X")
        assert len(cap.records) == 1
        assert cap.records[0].levelno == logging.INFO
        assert cap.records[0].getMessage() == "hello X"
        assert len(calls) == 0

        # WARNING hits both
        lw.warning("warn %s", "Y", extra={"k": 1})
        assert len(cap.records) == 2
        assert cap.records[1].levelno == logging.WARNING
        assert cap.records[1].getMessage() == "warn Y"
        assert len(calls) == 1
        lvl, msg, args, kwargs = calls[0]
        assert lvl == logging.WARNING
        assert msg == "warn %s"
        assert args == ("Y",)
        assert "extra" in kwargs
        assert kwargs["extra"] == {"k": 1}

        # ERROR still hits both; CRITICAL too
        lw.error("err")
        lw.critical("boom")
        assert any(r.levelno == logging.ERROR for r in cap.records)
        assert any(r.levelno == logging.CRITICAL for r in cap.records)
        assert any(c[0] == logging.ERROR for c in calls)
        assert any(c[0] == logging.CRITICAL for c in calls)
