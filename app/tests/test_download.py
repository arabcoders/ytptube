import logging
from pathlib import Path
from typing import Any

import pytest

from app.library.Download import Download, NestedLogger, Terminator
from app.library.ItemDTO import ItemDTO


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def make_item(id: str = "id1", title: str = "T", url: str = "http://u", folder: str = "f") -> ItemDTO:
    return ItemDTO(id=id, title=title, url=url, folder=folder)


class DummyQueue:
    def __init__(self) -> None:
        self.items: list[Any] = []

    def put(self, obj: Any) -> None:
        self.items.append(obj)

    def get(self) -> Any:
        if not self.items:
            return None
        return self.items.pop(0)


class TestNestedLogger:
    def test_debug_maps_levels_and_strips_prefix(self) -> None:
        logger = logging.getLogger("nl_test")
        logger.setLevel(logging.DEBUG)
        cap = CaptureHandler()
        # Remove existing handlers to avoid duplicates
        for h in list(logger.handlers):
            logger.removeHandler(h)
        logger.addHandler(cap)

        nl = NestedLogger(logger)
        nl.debug("[debug] detail")
        nl.debug("[download] progress")
        nl.debug("[info] info message")

        # Two DEBUG, one INFO
        levels = [r.levelno for r in cap.records]
        assert levels.count(logging.DEBUG) == 2
        assert levels.count(logging.INFO) == 1
        msgs = [r.getMessage() for r in cap.records]
        assert "[debug]" not in msgs[0]
        # [download] prefix is not stripped by NestedLogger
        assert msgs[1] == "[download] progress"
        assert msgs[2] == "info message"


class TestDownloadHooks:
    @pytest.fixture(autouse=True)
    def cfg_and_bus(self, monkeypatch: pytest.MonkeyPatch):
        # Minimal Config stub
        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 3600

            @staticmethod
            def get_instance():
                return Cfg

        monkeypatch.setattr("app.library.Download.Config", Cfg)

        # EventBus.get_instance is used during __init__ and start, we don't hit start here
        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.Download.EventBus", EB)

    def test_progress_hook_filters_fields(self) -> None:
        d = Download(make_item())
        q = DummyQueue()
        d.status_queue = q

        payload = {
            "tmpfilename": "t",
            "filename": "f",
            "status": "downloading",
            "msg": "m",
            "total_bytes": 10,
            "total_bytes_estimate": 12,
            "downloaded_bytes": 5,
            "speed": 1,
            "eta": 2,
            "other": "x",
        }
        d._progress_hook(payload)
        assert len(q.items) == 1
        ev = q.items[0]
        assert ev["id"] == d.id
        assert ev["action"] == "progress"
        # ensure only whitelisted keys included
        assert "other" not in ev
        for k in (
            "tmpfilename",
            "filename",
            "status",
            "msg",
            "total_bytes",
            "total_bytes_estimate",
            "downloaded_bytes",
            "speed",
            "eta",
        ):
            assert k in ev

    def test_postprocessor_hook_movefiles_sets_final_name(self, tmp_path: Path) -> None:
        d = Download(make_item())
        q = DummyQueue()
        d.status_queue = q

        finaldir = tmp_path / "out"
        finaldir.mkdir()
        path = finaldir / "file.mp4"
        # we don't need it to exist for this branch; hook doesn't check file existence
        payload = {
            "postprocessor": "MoveFiles",
            "status": "finished",
            "info_dict": {"__finaldir": str(finaldir), "filepath": str(path)},
        }
        d._postprocessor_hook(payload)
        assert len(q.items) == 1
        ev = q.items[0]
        assert ev["action"] == "moved"
        assert ev["status"] == "finished"
        assert ev["final_name"].endswith("file.mp4")

    def test_post_hooks_pushes_filename(self) -> None:
        d = Download(make_item())
        q = DummyQueue()
        d.status_queue = q
        d._post_hooks(None)
        assert len(q.items) == 0
        d._post_hooks("name.ext")
        assert len(q.items) == 1
        assert q.items[0]["filename"] == "name.ext"


class TestDownloadStale:
    @pytest.fixture(autouse=True)
    def cfg_and_bus(self, monkeypatch: pytest.MonkeyPatch):
        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 3600

            @staticmethod
            def get_instance():
                return Cfg

        monkeypatch.setattr("app.library.Download.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.Download.EventBus", EB)

    def test_is_stale_conditions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = Download(make_item())
        # Auto-start disabled is never stale
        d.info.auto_start = False
        assert d.is_stale() is False

        d.info.auto_start = True
        # Not started yet -> not stale
        d.started_time = 0
        assert d.is_stale() is False

        # Less than 300 seconds elapsed -> not stale
        d.started_time = 1000
        monkeypatch.setattr("time.time", lambda: 1200)
        assert d.is_stale() is False

        # Not running after 300s -> stale
        d.started_time = 0
        d.started_time = 1000
        monkeypatch.setattr("time.time", lambda: 1401)
        monkeypatch.setattr("app.library.Download.Download.running", lambda _self: False)
        d.info.status = "preparing"
        assert d.is_stale() is True

        # Running but status stuck -> stale
        monkeypatch.setattr("app.library.Download.Download.running", lambda _self: True)
        d.info.status = "queued"
        assert d.is_stale() is True

        # Running and in allowed statuses -> not stale
        for s in ("finished", "error", "cancelled", "downloading", "postprocessing"):
            d.info.status = s
            assert d.is_stale() is False


@pytest.mark.asyncio
async def test_start_initializes_and_emits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Cfg:
        debug = False
        ytdlp_debug = False
        max_workers = 1
        temp_keep = False
        temp_disabled = False
        download_info_expires = 3600

        @staticmethod
        def get_instance():
            return Cfg

        class _Mgr:
            @staticmethod
            def Queue():  # noqa: N802
                return DummyQueue()

        @staticmethod
        def get_manager():
            return Cfg._Mgr

    monkeypatch.setattr("app.library.Download.Config", Cfg)

    events = []

    class EB:
        @staticmethod
        def get_instance():
            return EB

        @staticmethod
        def emit(event, data=None, **_kwargs):
            events.append((event, data))

    monkeypatch.setattr("app.library.Download.EventBus", EB)

    class FakeProc:
        def __init__(self, name: str, target, *_args, **_kwargs):
            self.name = name
            self.target = target
            self.started = False

        def start(self) -> None:
            self.started = True

        def join(self) -> int:
            return 0

    monkeypatch.setattr("app.library.Download.multiprocessing.Process", FakeProc)

    item = make_item(id="start1")
    d = Download(item)
    d.temp_dir = str(tmp_path)
    d.download_dir = str(tmp_path)

    await d.start()

    assert d.info.status == "preparing"
    assert isinstance(d.status_queue, DummyQueue)
    assert d.temp_path is not None
    assert Path(d.temp_path).exists()
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_progress_update_processes_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cfg:
        debug = False
        ytdlp_debug = False
        max_workers = 1
        temp_keep = False
        temp_disabled = True
        download_info_expires = 3600

        @staticmethod
        def get_instance():
            return Cfg

    monkeypatch.setattr("app.library.Download.Config", Cfg)

    class EB:
        @staticmethod
        def get_instance():
            return EB

        @staticmethod
        def emit(*_a, **_kw):
            return None

    monkeypatch.setattr("app.library.Download.EventBus", EB)

    seen = []

    async def spy(_self, status):
        seen.append(status)

    d = Download(make_item(id="p1"))
    d.status_queue = DummyQueue()
    monkeypatch.setattr(Download, "_process_status_update", spy, raising=False)
    d.status_queue.put({"id": d.id, "status": "downloading"})
    d.status_queue.put({"id": d.id, "status": "postprocessing"})
    d.status_queue.put(Terminator())

    await d.progress_update()

    assert [s["status"] for s in seen] == ["downloading", "postprocessing"]


@pytest.mark.asyncio
async def test__process_status_update_finish_sets_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Cfg:
        debug = False
        ytdlp_debug = False
        max_workers = 1
        temp_keep = False
        temp_disabled = True
        download_info_expires = 3600

        @staticmethod
        def get_instance():
            return Cfg

    monkeypatch.setattr("app.library.Download.Config", Cfg)

    class EB:
        @staticmethod
        def get_instance():
            return EB

        @staticmethod
        def emit(*_a, **_kw):
            return None

    monkeypatch.setattr("app.library.Download.EventBus", EB)

    class FF:
        def has_video(self):
            return True

        def has_audio(self):
            return True

        metadata = {"duration": "7.9"}

    async def fake_ffprobe(_p):
        return FF()

    monkeypatch.setattr("app.library.Download.ffprobe", fake_ffprobe)

    d = Download(make_item(id="f1"))
    d.download_dir = str(tmp_path)
    path = Path(tmp_path) / "file.bin"
    path.write_bytes(b"x" * 10)

    await d._process_status_update({"id": d.id, "status": "finished", "final_name": str(path)})

    assert d.info.file_size == 10
    assert d.info.extras["is_video"] is True
    assert d.info.extras["is_audio"] is True
    assert d.info.extras["duration"] == int(7.9)
    assert isinstance(d.info.datetime, str)
