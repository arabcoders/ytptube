import asyncio
import logging
import os
import signal
import time
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import app.features.downloads.runtime.bootstrap as download_runtime
from app.features.downloads.items import Item, ItemDTO
from app.features.downloads.runtime.core import Download
from app.features.downloads.runtime.hooks import HookHandlers, NestedLogger
from app.features.downloads.runtime.pool_manager import PoolManager
from app.features.downloads.runtime.process_manager import ProcessManager
from app.features.downloads.runtime.queue_manager import DownloadQueue
from app.features.downloads.runtime.status_tracker import StatusTracker
from app.features.downloads.runtime.temp_manager import TempManager
from app.features.downloads.runtime.types import Terminator
from app.features.downloads.runtime.video_processor import add_video
from app.library.Events import EventBus, Events


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

    def get(self, timeout: float | None = None) -> Any:
        if not self.items:
            return None
        return self.items.pop(0)


class TestNestedLogger:
    def test_maps_levels_strips_prefix(self) -> None:
        logger = logging.getLogger("nl_test")
        logger.setLevel(logging.DEBUG)
        cap = CaptureHandler()
        for h in list(logger.handlers):
            logger.removeHandler(h)
        logger.addHandler(cap)

        nl = NestedLogger(logger)
        nl.debug("[debug] detail")
        nl.debug("[download] progress")
        nl.debug("[info] info message")

        levels = [r.levelno for r in cap.records]
        assert 2 == levels.count(logging.DEBUG), "Should have 2 debug messages"
        assert 1 == levels.count(logging.INFO), "Should have 1 info message"
        msgs = [r.getMessage() for r in cap.records]
        assert "[debug]" not in msgs[0], "[debug] prefix should be stripped"
        assert msgs[1] == "[download] progress", "[download] prefix is not stripped by NestedLogger"
        assert msgs[2] == "info message", "info message should have [info] prefix stripped"


class TestScheduledRetry:
    @staticmethod
    def queue(*, retry: int = 2, retry_fresh: bool = True, attempt: int = 0, continuedl: bool = True):
        from app.features.downloads.runtime.monitors import RETRYABLE_ERRORS

        info = make_item()
        info.status = "error"
        info.error = f"ERROR: {RETRYABLE_ERRORS[0]}"
        info.extras = {"retry_attempt": attempt}
        info.cli = "--format best"
        cast(Any, info).get_ytdlp_opts = lambda: SimpleNamespace(get_all=lambda: {"continuedl": continuedl})
        item = SimpleNamespace(info=info, is_live=False)
        queue: Any = SimpleNamespace(
            config=SimpleNamespace(retry=retry, retry_fresh=retry_fresh),
            is_paused=lambda: False,
            done=SimpleNamespace(empty=lambda: True, items=lambda: [], put=AsyncMock()),
            clear=AsyncMock(),
            add=AsyncMock(return_value={"status": "ok"}),
        )
        queue.done.get_many_by_status = AsyncMock(return_value=[(info._id, item)])
        return queue

    def test_retryable_error(self) -> None:
        from app.features.downloads.runtime.monitors import is_retryable_error

        assert is_retryable_error("HTTP Error 403: Forbidden")
        assert is_retryable_error("4102066 bytes read, 6199501 more expected")
        assert not is_retryable_error("Unable to extract video")

    @pytest.mark.asyncio
    async def test_retry(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue = self.queue()
        await check_retries(queue)

        retry = queue.add.await_args.kwargs["item"]
        assert retry.extras["retry_attempt"] == 1
        assert retry.cli == "--format best"
        assert retry.requeued is True

    @pytest.mark.asyncio
    async def test_retry_fresh(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue = self.queue(attempt=1)
        await check_retries(queue)

        retry = queue.add.await_args.kwargs["item"]
        assert retry.extras["retry_attempt"] == 2
        assert retry.cli == "--format best\n--no-continue"

    @pytest.mark.asyncio
    async def test_retry_already_fresh(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue = self.queue(retry=1, continuedl=False)
        await check_retries(queue)

        retry = queue.add.await_args.kwargs["item"]
        assert retry.extras["retry_attempt"] == 1
        assert retry.cli == "--format best"

    @pytest.mark.asyncio
    async def test_retry_limit(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue = self.queue(attempt=2)
        await check_retries(queue)

        queue.clear.assert_not_awaited()
        queue.add.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_skips_live(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue = self.queue()
        queue.done.get_many_by_status.return_value[0][1].is_live = True
        await check_retries(queue)

        queue.add.assert_not_awaited()


class TestRetry:
    @pytest.mark.asyncio
    async def test_batch(self) -> None:
        info = make_item()
        info.status = "error"
        item = Download(info=info)
        queue: Any = SimpleNamespace(
            done=SimpleNamespace(
                get_many_by_ids=AsyncMock(return_value=[(info._id, item)]),
                get_many_by_status=AsyncMock(),
                bulk_delete=AsyncMock(return_value=1),
            ),
            add=AsyncMock(return_value={"status": "ok"}),
            config=SimpleNamespace(extract_info_concurrency=2),
            _notify=Mock(),
            _retry_lock=asyncio.Lock(),
            _retry_limit=asyncio.Semaphore(2),
        )
        queue._finish_retry = DownloadQueue._finish_retry.__get__(queue)

        with patch("app.features.downloads.runtime.queue_manager.asyncio.create_task") as spawn:
            count = await DownloadQueue.retry(queue, ids=[info._id])
            await spawn.call_args.args[0]

        assert count == 1
        queue.done.bulk_delete.assert_awaited_once_with([info._id])
        retry = queue.add.await_args.args[0]
        assert retry.url == info.url
        assert retry.requeued is True
        events = queue._notify.emit.call_args_list
        assert events[0].args[0] == Events.LOG_INFO
        assert events[0].kwargs["data"]["items"][0]["title"] == info.title
        assert events[-1].args[0] == Events.LOG_SUCCESS

    @pytest.mark.asyncio
    async def test_limit(self) -> None:
        active = 0
        peak = 0

        async def add(_: Item) -> dict[str, str]:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"status": "ok"}

        items = []
        for index in range(5):
            info = make_item(id=str(index))
            info.status = "error"
            items.append((info._id, Download(info=info)))

        queue: Any = SimpleNamespace(
            add=add,
            config=SimpleNamespace(extract_info_concurrency=2),
            _notify=Mock(),
            _retry_limit=asyncio.Semaphore(2),
        )
        await asyncio.gather(DownloadQueue._finish_retry(queue, items), DownloadQueue._finish_retry(queue, items))

        assert peak == 2

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        queue: Any = SimpleNamespace(
            done=SimpleNamespace(get_many_by_ids=AsyncMock(return_value=[])),
            _retry_lock=asyncio.Lock(),
        )

        assert await DownloadQueue.retry(queue, ids=["missing"]) == 0


class TestDownloadHooks:
    @pytest.fixture(autouse=True)
    def cfg_and_bus(self, monkeypatch: pytest.MonkeyPatch):
        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 0

            @staticmethod
            def get_instance():
                return Cfg

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.features.downloads.runtime.core.EventBus", EB)

    def test_progress_hook_filters_fields(self) -> None:
        d = Download(make_item())
        q = DummyQueue()
        hooks = HookHandlers(d.id, cast(Any, q), d.logger, d.debug)

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
        hooks.progress_hook(payload)
        assert 1 == len(q.items), "Should have 1 item in queue"
        ev = q.items[0]
        assert ev["id"] == d.id, "Event should have correct download ID"
        assert ev["action"] == "progress", "Action should be 'progress'"
        assert "other" not in ev, "Non-whitelisted keys should not be included in event"
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
            assert k in ev, f"Key '{k}' should be in event"

    def test_post_hooks_pushes_filename(self) -> None:
        d = Download(make_item())
        q = DummyQueue()
        hooks = HookHandlers(d.id, cast(Any, q), d.logger, d.debug)
        hooks.post_hook("name.ext")
        assert 1 == len(q.items), "Should have 1 item when filename is provided"
        assert q.items[0]["final_name"] == "name.ext", "Filename should match"


class TestDownloadStale:
    @pytest.fixture(autouse=True)
    def cfg_and_bus(self, monkeypatch: pytest.MonkeyPatch):
        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 0

            @staticmethod
            def get_instance():
                return Cfg

            @staticmethod
            def get_manager():
                # Return a mock manager with Queue method
                mock_manager = MagicMock()
                mock_manager.Queue = MagicMock(return_value=DummyQueue())
                return mock_manager

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.features.downloads.runtime.core.EventBus", EB)

    def test_is_stale_conditions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = Download(make_item())

        d.info.auto_start = False
        assert d.is_stale() is False, "Download with auto_start disabled should not be stale"

        d.info.auto_start = True
        d.started_time = 0
        assert d.is_stale() is False, "Download that has not been started should not be stale"

        d.started_time = 1000
        monkeypatch.setattr("time.time", lambda: 1200)
        assert d.is_stale() is False, "Download running for less than 300 seconds should not be stale"

        monkeypatch.setattr("time.time", lambda: 1401)

        d.info.status = "finished"
        assert d.is_stale() is False, "Download with status 'finished' should not be stale regardless of process state"

        d.info.status = "error"
        assert d.is_stale() is False, "Download with status 'error' should not be stale regardless of process state"

        d.info.status = "cancelled"
        assert d.is_stale() is False, "Download with status 'cancelled' should not be stale regardless of process state"

        d.info.status = "downloading"
        assert d.is_stale() is False, (
            "Download with status 'downloading' should not be stale regardless of process state"
        )

        d.info.status = "postprocessing"
        assert d.is_stale() is False, (
            "Download with status 'postprocessing' should not be stale regardless of process state"
        )

        d.info.status = "preparing"
        assert d.is_stale() is True, (
            "Download with status 'preparing' and no running process after 300s should be stale"
        )

        d.info.status = "queued"
        assert d.is_stale() is True, "Download with status 'queued' and no running process after 300s should be stale"

        d.info.status = None
        assert d.is_stale() is True, "Download with no status and no running process after 300s should be stale"

    @pytest.mark.asyncio
    async def test_time_set_main_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
        d = Download(make_item())

        # Create a mock process
        mock_proc = MagicMock()
        mock_proc.join = MagicMock(return_value=0)

        # Create a proper mock for create_task that consumes the coroutine
        created_tasks = []

        def mock_create_task(coro, **kwargs):
            # Close the coroutine to avoid warning
            coro.close()
            task = MagicMock()
            created_tasks.append(task)
            return task

        # Mock process manager to avoid actually starting a subprocess
        with (
            patch.object(d._process_manager, "create_process", return_value=mock_proc) as mock_create,
            patch.object(d._process_manager, "start") as mock_start,
            patch("asyncio.create_task", side_effect=mock_create_task) as mock_create_task_fn,
            patch("asyncio.get_running_loop") as mock_loop,
        ):
            # Set the mock proc on the process manager
            d._process_manager.proc = mock_proc

            # Mock the join to return immediately
            async def mock_executor(*args):
                return 0

            mock_loop.return_value.run_in_executor = mock_executor

            # Mock status tracker to prevent actual status updates
            d._status_tracker = MagicMock()
            d._status_tracker.final_update = True

            assert d.started_time == 0, "started_time should be 0 before start() is called"

            # Call start() - this should set started_time in the main process
            await d.start()

            # Verify started_time was set to a non-zero value
            assert d.started_time > 0, "started_time should be set in main process after start() is called"

            # Verify process was actually started
            mock_create.assert_called_once()
            mock_start.assert_called_once()


class TestDownloadClose:
    @staticmethod
    def make_download(*, started: bool = True) -> tuple[Any, Mock, Mock]:
        download: Any = object.__new__(Download)
        download.info = make_item()
        download.id = download.info._id
        download.logger = Mock()
        download.status_queue = Mock()
        download._status_tracker = Mock()
        download._hook_handlers = Mock()
        download._temp_manager = Mock()
        download._process_manager = Mock(cancel_in_progress=False)
        download._process_manager.started.return_value = started
        download._process_manager.close = AsyncMock()
        return download, download.status_queue, download._status_tracker

    @pytest.mark.asyncio
    async def test_close_queue(self) -> None:
        download, status_queue, tracker = self.make_download()

        assert await download.close() is True

        tracker.cancel_update_task.assert_called_once_with()
        tracker.put_terminator.assert_called_once_with()
        status_queue.close.assert_called_once_with()
        status_queue.join_thread.assert_called_once_with()
        assert download.status_queue is None
        assert download._status_tracker is None
        assert download._hook_handlers is None

    @pytest.mark.asyncio
    async def test_close_queue_on_error(self) -> None:
        download, status_queue, tracker = self.make_download()
        download._process_manager.close.side_effect = RuntimeError("close failed")

        assert await download.close() is False

        tracker.put_terminator.assert_called_once_with()
        status_queue.close.assert_called_once_with()
        status_queue.join_thread.assert_called_once_with()
        assert download.status_queue is None

    @pytest.mark.asyncio
    async def test_close_partial_queue(self) -> None:
        download, status_queue, _ = self.make_download(started=False)
        download._status_tracker = None

        assert await download.close() is False

        status_queue.put.assert_called_once()
        assert isinstance(status_queue.put.call_args.args[0], Terminator)
        status_queue.close.assert_called_once_with()
        status_queue.join_thread.assert_called_once_with()


class TestDownloadFlow:
    def test_download_bootstraps_before_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.presets.models import PresetModel
        from app.features.presets.service import Presets

        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 3600
            download_path = "/downloads"
            temp_path = "/tmp"
            output_template = "%(title)s.%(ext)s"
            output_template_chapter = "%(title)s.%(ext)s"

            @staticmethod
            def get_instance():
                return Cfg

            @staticmethod
            def get_replacers():
                return {
                    "os_sep": os.path.sep,
                    "download_path": Cfg.download_path,
                    "temp_path": Cfg.temp_path,
                    "config_path": "/config",
                    "archive_file": "/config/archive.log",
                }

        Presets._reset_singleton()
        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)
        monkeypatch.setattr("app.features.ytdlp.ytdlp_opts.Config", Cfg)

        def bootstrap(*, logger=None):
            del logger
            preset = PresetModel(
                id=1,
                name="native",
                description="",
                folder="",
                template="",
                cookies="",
                cli="--format worst",
                default=False,
                priority=0,
            )
            asyncio.run(Presets.get_instance().refresh_cache([preset]))
            return True

        monkeypatch.setattr("app.features.downloads.runtime.core.ensure_download_runtime", bootstrap)

        item = make_item()
        item.preset = "native"
        download = Download(
            info=item,
            info_dict={
                "id": "test-id",
                "url": "http://u",
                "formats": [{"format_id": "18"}],
                "epoch": int(time.time()),
            },
        )
        download.status_queue = cast(Any, DummyQueue())
        download._hook_handlers = Mock(
            progress_hook=Mock(),
            postprocessor_hook=Mock(),
            post_hook=Mock(),
        )

        captured: dict[str, Any] = {}

        class FakeYTDLP:
            def __init__(self, params):
                captured["params"] = params
                self._download_retcode = 0
                self._interrupted = False

            def process_ie_result(self, ie_result, download):
                return ie_result, download

        monkeypatch.setattr("app.features.downloads.runtime.core.YTDLP", FakeYTDLP)

        try:
            download._download()
        finally:
            Presets._reset_singleton()

        assert captured["params"]["format"] == "worst"

    def test_pushes_download_skipped_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        download = Download(
            info=make_item(),
            info_dict={
                "id": "test-id",
                "url": "http://u",
                "formats": [{"format_id": "18"}],
                "epoch": int(time.time()),
            },
        )
        download.status_queue = cast(Any, DummyQueue())
        download._hook_handlers = Mock(
            progress_hook=Mock(),
            postprocessor_hook=Mock(),
            post_hook=Mock(),
        )
        download_any: Any = download.info
        download_any.get_ytdlp_opts = Mock(
            return_value=Mock(
                add=Mock(
                    return_value=Mock(
                        get_all=Mock(return_value={"skip_download": True}),
                    )
                )
            )
        )

        class FakeYTDLP:
            def __init__(self, params, enable_custom_outtmpl=False):
                self.params = params
                self.enable_custom_outtmpl = enable_custom_outtmpl
                self._download_retcode = 0
                self._interrupted = False

            def process_ie_result(self, ie_result, download):
                return ie_result, download

        monkeypatch.setattr("app.features.downloads.runtime.core.YTDLP", FakeYTDLP)

        download._download()

        queue = cast(DummyQueue, download.status_queue)
        assert queue.items[0]["download_skipped"] is True
        assert queue.items[1]["status"] == "finished"
        assert queue.items[1]["download_skipped"] is True

    def test_playlist_extras(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Cfg:
            debug = False
            ytdlp_debug = False
            max_workers = 1
            temp_keep = False
            temp_disabled = True
            download_info_expires = 0

            @staticmethod
            def get_instance():
                return Cfg

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        item = make_item()
        item.extras = {
            "playlist": "Internet Dating Slang",
            "playlist_title": "Internet Dating Slang",
            "playlist_index": 1,
            "playlist_autonumber": 1,
            "n_entries": 2,
        }
        download = Download(
            info=item,
            info_dict={
                "id": "test-id",
                "url": "http://u",
                "title": "Video Title",
                "formats": [{"format_id": "18"}],
                "playlist": "NA",
                "playlist_title": None,
                "playlist_index": "NA",
                "playlist_autonumber": "",
                "n_entries": None,
            },
        )
        download.status_queue = cast(Any, DummyQueue())
        download._hook_handlers = Mock(
            progress_hook=Mock(),
            postprocessor_hook=Mock(),
            post_hook=Mock(),
        )
        download_any2: Any = download.info
        download_any2.get_ytdlp_opts = Mock(
            return_value=Mock(add=Mock(return_value=Mock(get_all=Mock(return_value={}))))
        )

        captured: dict[str, Any] = {}

        class FakeYTDLP:
            def __init__(self, params):
                self.params = params
                self._download_retcode = 0
                self._interrupted = False

            def process_ie_result(self, ie_result, download):
                captured["ie_result"] = ie_result
                return ie_result, download

        monkeypatch.setattr("app.features.downloads.runtime.core.YTDLP", FakeYTDLP)

        download._download()

        ie_result = captured["ie_result"]
        assert ie_result["playlist"] == "Internet Dating Slang"
        assert ie_result["playlist_title"] == "Internet Dating Slang"
        assert ie_result["playlist_index"] == 1
        assert ie_result["playlist_autonumber"] == 1
        assert ie_result["n_entries"] == 2

    @pytest.mark.asyncio
    async def test_download_flow_inline_process(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

            @staticmethod
            def get_manager():
                class DummyManager:
                    def Queue(self):
                        return DummyQueue()

                return DummyManager()

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.features.downloads.runtime.core.EventBus", EB)

        item = ItemDTO(
            id="id1",
            title="T",
            url="http://u",
            folder="f",
            download_dir=str(tmp_path),
            temp_dir=str(tmp_path),
        )
        download = Download(info=item)
        monkeypatch.setattr(download._process_manager, "create_queue", lambda: DummyQueue())
        final_file = tmp_path / "video.mp4"
        final_file.write_text("test content")

        async def fake_ffprobe(_file: Path):
            await asyncio.sleep(0.01)
            return SimpleNamespace(
                metadata={"duration": "10"},
                video=[SimpleNamespace(width=1280, height=720, framerate=30, codec_name="h264")],
                audio=[],
                has_video=lambda: True,
                has_audio=lambda: False,
            )

        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe", fake_ffprobe)
        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe_bin", lambda: "/usr/bin/ffprobe")

        def fake_download():
            queue = download.status_queue
            assert queue is not None
            queue = cast(Any, queue)
            queue.put(
                {
                    "id": download.id,
                    "status": "downloading",
                    "downloaded_bytes": 10,
                    "total_bytes": 10,
                }
            )
            download._status_tracker = StatusTracker(
                info=download.info,
                download_id=download.id,
                download_dir=str(tmp_path),
                temp_path=None,
                status_queue=queue,
                logger=download.logger,
                debug=False,
            )
            queue.put(
                {
                    "id": download.id,
                    "status": "finished",
                    "final_name": str(final_file),
                }
            )
            queue.put(Terminator())

        download_mock: Any = download
        download_mock._download = fake_download

        class InlineProcess:
            def __init__(self, target):
                self._target = target
                self.pid = 12345
                self.ident = 12345

            def start(self):
                self._target()

            def join(self):
                return 0

            def is_alive(self):
                return False

            def terminate(self):
                return None

            def kill(self):
                return None

            def close(self):
                return None

        def create_process(target):
            inline_proc = InlineProcess(target)
            download._process_manager.proc = cast(Any, inline_proc)
            return download._process_manager.proc

        def start_process():
            assert download._process_manager.proc is not None
            download._process_manager.proc.start()

        monkeypatch.setattr(download._process_manager, "create_process", create_process)
        monkeypatch.setattr(download._process_manager, "start", start_process)

        await download.start()

        assert download.info.status == "finished", "Download should finish via inline process"
        assert download.info.filename == "video.mp4", "Final filename should be set from status update"
        assert download.info.extras["media_profile"] == {
            "video": {"width": 1280, "height": 720, "fps": 30, "codec": "h264"}
        }

    @pytest.mark.asyncio
    async def test_live_cancel_drains_final(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

            @staticmethod
            def get_manager():
                class DummyManager:
                    def Queue(self):
                        return DummyQueue()

                return DummyManager()

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.features.downloads.runtime.core.EventBus", EB)

        item = ItemDTO(
            id="id-live",
            title="Live",
            url="http://u",
            folder="f",
            download_dir=str(tmp_path),
            temp_dir=str(tmp_path),
            is_live=True,
        )
        download = Download(info=item)
        monkeypatch.setattr(download._process_manager, "create_queue", lambda: DummyQueue())
        final_file = tmp_path / "live.mp4"
        final_file.write_text("test content")

        def fake_download():
            queue = cast(Any, download.status_queue)
            queue.put({"id": download.id, "status": "downloading", "downloaded_bytes": 10})
            queue.put({"id": download.id, "status": "finished", "final_name": str(final_file)})
            queue.put(Terminator())

        download_mock: Any = download
        download_mock._download = fake_download

        class InlineProcess:
            def __init__(self, target):
                self._target = target
                self.pid = 12345
                self.ident = 12345

            def start(self):
                self._target()

            def join(self):
                return 0

            def is_alive(self):
                return False

            def terminate(self):
                return None

            def kill(self):
                return None

            def close(self):
                return None

        def create_process(target):
            inline_proc = InlineProcess(target)
            download._process_manager.proc = cast(Any, inline_proc)
            return download._process_manager.proc

        def start_process():
            assert download._process_manager.proc is not None
            download._process_manager.proc.start()
            download._process_manager.cancelled = True

        def mock_create_task(coro, **_kwargs):
            coro.close()
            return MagicMock()

        monkeypatch.setattr(download._process_manager, "create_process", create_process)
        monkeypatch.setattr(download._process_manager, "start", start_process)
        monkeypatch.setattr("asyncio.create_task", mock_create_task)

        await download.start()

        assert download.info.status == "finished", "Final live file should win over cancel state"
        assert download.info.filename == "live.mp4", "Finalized live filename should be preserved"

    @pytest.mark.asyncio
    async def test_regular_cancel_skips_drain(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

            @staticmethod
            def get_manager():
                class DummyManager:
                    def Queue(self):
                        return DummyQueue()

                return DummyManager()

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.features.downloads.runtime.core.EventBus", EB)

        tracker = Mock()
        tracker.final_update = False
        tracker.drain_queue = AsyncMock()

        async def progress_update():
            return None

        tracker.progress_update = progress_update

        monkeypatch.setattr("app.features.downloads.runtime.core.StatusTracker", Mock(return_value=tracker))
        monkeypatch.setattr("app.features.downloads.runtime.core.HookHandlers", Mock())

        download = Download(make_item(id="regular-id"))
        monkeypatch.setattr(download._process_manager, "create_queue", lambda: DummyQueue())

        mock_proc = Mock()

        def join_process():
            # Cancellation cleanup may clear the instance reference before start() resumes.
            download._status_tracker = None
            return 0

        mock_proc.join = Mock(side_effect=join_process)

        def start_process():
            download._process_manager.cancelled = True

        def mock_create_task(coro, **_kwargs):
            coro.close()
            return MagicMock()

        monkeypatch.setattr(download._process_manager, "create_process", Mock(return_value=mock_proc))
        monkeypatch.setattr(download._process_manager, "start", start_process)
        monkeypatch.setattr("asyncio.create_task", mock_create_task)

        download._process_manager.proc = mock_proc

        await download.start()

        tracker.drain_queue.assert_not_awaited()
        assert download.info.status == "cancelled", "Regular cancels should keep the fast cancel path"


class TestDownloadSpawnPickling:
    def setup_method(self):
        EventBus._reset_singleton()

    def test_spawn_pickling_ignores_listener(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

        monkeypatch.setattr("app.features.downloads.runtime.core.Config", Cfg)

        bus = EventBus.get_instance()

        def local_event_handler(_event, _name, **_kwargs):
            return None

        bus.subscribe(Events.LOG_INFO, local_event_handler, "local-event-handler")

        item = ItemDTO(
            id="id1",
            title="T",
            url="http://u",
            folder="f",
            download_dir=str(tmp_path),
            temp_dir=str(tmp_path),
        )
        download = Download(info=item)
        download.status_queue = cast(Any, DummyQueue())
        assert download.status_queue is not None
        download._status_tracker = StatusTracker(
            info=item,
            download_id=download.id,
            download_dir=str(tmp_path),
            temp_path=None,
            status_queue=cast(Any, download.status_queue),
            logger=download.logger,
            debug=False,
        )

        state = download.__getstate__()
        assert state.get("_status_tracker") is None, "StatusTracker should be excluded from pickled state"

        ForkingPickler.dumps(download._download)


class TestDownloadRuntime:
    def test_fork_skip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(download_runtime._BOOTSTRAP_STATE, "pid", None)
        monkeypatch.setattr(
            download_runtime.multiprocessing,
            "current_process",
            lambda: SimpleNamespace(name="download-test"),
        )
        monkeypatch.setattr(download_runtime.multiprocessing, "get_start_method", lambda allow_none=True: "fork")
        run = Mock()
        monkeypatch.setattr(download_runtime, "_run_bootstrap", run)

        assert download_runtime.ensure_download_runtime() is False
        run.assert_not_called()

    def test_spawn_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(download_runtime._BOOTSTRAP_STATE, "pid", None)
        monkeypatch.setattr(
            download_runtime.multiprocessing,
            "current_process",
            lambda: SimpleNamespace(name="download-test"),
        )
        monkeypatch.setattr(download_runtime.multiprocessing, "get_start_method", lambda allow_none=True: "spawn")
        monkeypatch.setattr(download_runtime.os, "getpid", lambda: 123)
        run = Mock()
        monkeypatch.setattr(download_runtime, "_run_bootstrap", run)

        assert download_runtime.ensure_download_runtime() is True
        assert download_runtime.ensure_download_runtime() is False
        run.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_bootstrap_loads_presets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = SimpleNamespace(db_file="/tmp/test.db")
        store = SimpleNamespace(get_connection=AsyncMock())
        repo = SimpleNamespace(all=AsyncMock(return_value=["preset"]))
        presets = SimpleNamespace(refresh_cache=AsyncMock())

        monkeypatch.setattr(download_runtime, "Config", SimpleNamespace(get_instance=lambda: config))
        monkeypatch.setattr(
            download_runtime,
            "SqliteStore",
            SimpleNamespace(get_instance=lambda db_path=None: store),
        )
        monkeypatch.setattr(
            download_runtime,
            "PresetsRepository",
            SimpleNamespace(get_instance=lambda: repo),
        )
        monkeypatch.setattr(download_runtime, "Presets", SimpleNamespace(get_instance=lambda: presets))

        await download_runtime._bootstrap_download_runtime()

        store.get_connection.assert_awaited_once_with()
        repo.all.assert_awaited_once_with()
        presets.refresh_cache.assert_awaited_once_with(["preset"])


class TestTempManager:
    def test_create_temp_path_disabled(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, "/tmp", temp_disabled=True, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is None, "Should return None when temp_disabled is True"
        assert tm.temp_path is None, "temp_path should remain None when disabled"

    def test_temp_path_no_dir(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, None, temp_disabled=False, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is None, "Should return None when temp_dir is None"
        assert tm.temp_path is None, "temp_path should remain None when no temp_dir"

    def test_temp_path_creates_directory(self, tmp_path: Path) -> None:
        info = make_item(id="test123")
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is not None, "Should return Path when enabled"
        assert result.exists(), "Temporary directory should be created"
        assert result.parent == tmp_path, "Temp directory should be created in temp_dir"
        assert tm.temp_path == result, "temp_path should be set to created path"

    def test_path_uses_consistent_hash(self, tmp_path: Path) -> None:
        info = make_item(id="test123")
        logger = logging.getLogger("test")
        tm1 = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm2 = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)

        path1 = tm1.create_temp_path()
        path2 = tm2.create_temp_path()
        assert path1 == path2, "Same download ID should produce same temp path"

    def test_delete_temp_disabled(self, tmp_path: Path) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=True, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should not delete when temp_disabled is True"

    def test_delete_temp_keep(self, tmp_path: Path) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=True, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should not delete when temp_keep is True"

    def test_delete_temp_no_path(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, "/tmp", temp_disabled=False, temp_keep=False, logger=logger)

        tm.delete_temp()
        assert tm.temp_path is None, "temp_path should stay unset"

    def test_temp_keeps_partial_download(self, tmp_path: Path) -> None:
        info = make_item()
        info.status = "downloading"
        info.downloaded_bytes = 1000
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should keep temp dir for partial download"

    def test_delete_temp_with_bypass(self, tmp_path: Path) -> None:
        info = make_item()
        info.status = "downloading"
        info.downloaded_bytes = 1000
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()
        (tm.temp_path / "file.txt").write_text("test")

        tm.delete_temp(by_pass=True)
        assert tm.temp_path.exists(), "Directory should still exist with bypass"
        assert not (tm.temp_path / "file.txt").exists(), "Contents should be deleted with bypass"

    def test_delete_temp_finished_download(self, tmp_path: Path) -> None:
        info = make_item()
        info.status = "finished"
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert not tm.temp_path.exists(), "Should delete temp dir for finished download"

    def test_refuses_delete_temp_root(self, tmp_path: Path) -> None:
        info = make_item()
        info.status = "finished"
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should refuse to delete temp root directory"


class TestProcessManager:
    def test_create_process(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.cancel_event.set()

        def dummy_target():
            pass

        proc = pm.create_process(dummy_target)
        assert proc is not None, "Should create a process"
        assert pm.proc is proc, "Should store process reference"
        assert pm.cancel_event.is_set() is False, "Should clear stale cancel events before starting"
        assert "download-test-id" == proc.name, "Process name should include download ID"

    def test_started(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        assert pm.started() is False, "Should return False when no process created"

        pm.create_process(lambda: None)
        assert pm.started() is True, "Should return True after process created"

    def test_running_no_process(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        assert pm.running() is False, "Should return False when no process"

    def test_is_cancelled_default(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        assert pm.is_cancelled() is False, "Should return False by default"

    def test_cancel_marks_as_cancelled(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.proc.is_alive = Mock(return_value=False)

        result = pm.cancel()
        assert pm.is_cancelled() is True, "Should mark as cancelled"

    def test_cancel_not_started(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = pm.cancel()
        assert result is False, "Should return False when process not started"
        assert pm.is_cancelled() is False, "Should not mark as cancelled when not started"

    def test_kill_not_running(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = pm.kill()
        assert result is False, "Should return False when process not running"

    def test_kill_sends_sigusr1_posix(self) -> None:
        if "posix" != os.name:
            pytest.skip("Test only runs on POSIX systems")

        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.proc.pid = 12345
        pm.proc.ident = 67890
        pm.proc.is_alive = Mock(side_effect=[True, False, False])

        with patch("app.features.downloads.runtime.process_manager.os.kill") as mock_kill:
            result = pm.kill()
            mock_kill.assert_called_once_with(12345, signal.SIGUSR1)
            assert result is True, "Should return True when process killed successfully"

    def test_kill_live_uses_event(self) -> None:
        logger = logging.getLogger("test")
        pm_live = ProcessManager("test-id", is_live=True, logger=logger)
        pm_regular = ProcessManager("test-id", is_live=False, logger=logger)

        pm_live.proc = Mock()
        pm_live.proc.pid = 12345
        pm_live.proc.ident = 67890
        pm_live.proc.is_alive = Mock(return_value=True)

        pm_regular.proc = Mock()
        pm_regular.proc.pid = 12346
        pm_regular.proc.ident = 67891
        pm_regular.proc.is_alive = Mock(return_value=True)

        with (
            patch("app.features.downloads.runtime.process_manager.os.kill") as mock_kill,
            patch(
                "app.features.downloads.runtime.process_manager.wait_for_process_with_timeout", return_value=True
            ) as mock_wait,
        ):
            assert pm_live.kill() is True, "Live downloads should stop via the shared cancel event"
            assert pm_live.cancel_event.is_set() is True, "Live kill should signal the worker cancel event"
            mock_kill.assert_not_called()
            mock_wait.assert_called_once_with(pm_live.proc, 10)

        if "posix" != os.name:
            pytest.skip("Regular SIGUSR1 path only runs on POSIX systems")

        with (
            patch("app.features.downloads.runtime.process_manager.os.kill") as mock_kill,
            patch(
                "app.features.downloads.runtime.process_manager.wait_for_process_with_timeout", return_value=True
            ) as mock_wait,
        ):
            assert pm_regular.kill() is True, "Regular downloads should keep SIGUSR1 behavior"
            mock_kill.assert_called_once_with(12346, signal.SIGUSR1)
            mock_wait.assert_called_once_with(pm_regular.proc, 5)

    @pytest.mark.asyncio
    async def test_close_not_started(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = await pm.close()
        assert result is False, "Should return False when process not started"

    @pytest.mark.asyncio
    async def test_close_during_cancel(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.cancel_in_progress = True

        result = await pm.close()
        assert result is False, "Should return False when cancellation already in progress"

    @pytest.mark.asyncio
    async def test_close_kills_joins_process(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.proc.ident = 12345
        pm.proc.is_alive = Mock(side_effect=[False, False])
        pm.proc.join = Mock()
        pm.proc.close = Mock()

        result = await pm.close()
        assert result is True, "Should return True on successful close"
        assert pm.proc is None, "Process reference should be cleared"


class TestStatusTracker:
    @pytest.fixture
    def mock_config(self):
        return {
            "info": make_item(id="test-id"),
            "download_id": "test-id",
            "download_dir": "/downloads",
            "temp_path": None,
            "status_queue": DummyQueue(),
            "logger": logging.getLogger("test"),
            "debug": False,
        }

    def test_init_sets_attributes(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        assert st.id == "test-id", "Should set download ID"
        assert st.info == mock_config["info"], "Should set info reference"
        assert st.tmpfilename is None, "Should initialize tmpfilename as None"
        assert st.final_update is False, "Should initialize final_update as False"

    @pytest.mark.asyncio
    async def test_status_ignores_bad_id(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "wrong-id", "status": "downloading"}

        await st.process_status_update(status)
        assert st.info.status != "downloading", "Should not update status for wrong ID"

    @pytest.mark.asyncio
    async def test_status_ignores_short(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id"}

        await st.process_status_update(status)

    @pytest.mark.asyncio
    async def test_status_update_sets_status(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "downloaded_bytes": 1000}

        await st.process_status_update(status)
        assert st.info.status == "downloading", "Should update info status"

    @pytest.mark.asyncio
    async def test_status_sets_skipped(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "download_skipped": True}

        await st.process_status_update(status)
        assert st.info.download_skipped is True, "Should update download_skipped from status queue"

    @pytest.mark.asyncio
    async def test_status_update_sets_tmpfilename(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "tmpfilename": "/tmp/file.part"}

        await st.process_status_update(status)
        assert st.tmpfilename == "/tmp/file.part", "Should update tmpfilename"

    @pytest.mark.asyncio
    async def test_status_sets_percent(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {
            "id": "test-id",
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
        }

        await st.process_status_update(status)
        assert st.info.downloaded_bytes == 50, "Should set downloaded_bytes"
        assert st.info.total_bytes == 100, "Should set total_bytes"
        assert st.info.percent == 50.0, "Should calculate percent correctly"

    @pytest.mark.asyncio
    async def test_status_uses_estimate(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {
            "id": "test-id",
            "status": "downloading",
            "downloaded_bytes": 30,
            "total_bytes_estimate": 100,
        }

        await st.process_status_update(status)
        assert st.info.total_bytes == 100, "Should use total_bytes_estimate when total_bytes not available"
        assert st.info.percent == 30.0, "Should calculate percent from estimate"

    @pytest.mark.asyncio
    async def test_status_percent(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {
            "id": "test-id",
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
        }

        await st.process_status_update(status)
        assert st.info.percent == 50.0, "Should calculate percent correctly with valid total"

    @pytest.mark.asyncio
    async def test_status_sets_speed_eta(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "speed": 1024000, "eta": 60}

        await st.process_status_update(status)
        assert st.info.speed == 1024000, "Should set speed"
        assert st.info.eta == 60, "Should set eta"

    @pytest.mark.asyncio
    async def test_status_update_sets_error(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "error", "error": "Download failed"}

        await st.process_status_update(status)
        assert st.info.status == "error", "Should set status to error"
        assert st.info.error == "Download failed", "Should set error message"

    @pytest.mark.asyncio
    async def test_update_sets_final_update(self, tmp_path: Path, mock_config: dict[str, Any]) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")

        st = StatusTracker(**mock_config)
        st.download_dir = str(tmp_path)
        status = {"id": "test-id", "status": "finished", "final_name": str(test_file)}

        await st.process_status_update(status)
        assert st.final_update is True, "Should set final_update when final file exists"
        assert st.info.filename == "test.mp4", "Should set relative filename"

    @pytest.mark.asyncio
    async def test_media_profile(
        self, tmp_path: Path, mock_config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")
        seen: dict[str, bool] = {}

        async def fake_ffprobe(_file: Path):
            seen["final_update"] = st.final_update
            return SimpleNamespace(
                metadata={"duration": "42.5"},
                video=[SimpleNamespace(width=1920, height=1080, framerate=60, codec_name="h264")],
                audio=[SimpleNamespace(bit_rate="320000", codec_name="aac", channels=2, sample_rate="48000")],
                has_video=lambda: True,
                has_audio=lambda: True,
            )

        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe", fake_ffprobe)
        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe_bin", lambda: "/usr/bin/ffprobe")

        st = StatusTracker(**mock_config)
        st.download_dir = str(tmp_path)
        status = {"id": "test-id", "status": "finished", "final_name": str(test_file)}

        await st.process_status_update(status)

        assert st.info.extras["media_profile"] == {
            "video": {"width": 1920, "height": 1080, "fps": 60, "codec": "h264"},
            "audio": {"bitrate": "320000", "codec": "aac", "channels": 2, "sample_rate": "48000"},
        }
        assert st.info.extras["duration"] == 42
        assert seen["final_update"] is False

    @pytest.mark.asyncio
    async def test_finalize_skips_missing_ffprobe(
        self, tmp_path: Path, mock_config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")

        def fail_if_probed(_file: Path):
            raise AssertionError("ffprobe must not run when the binary is unavailable")

        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe", fail_if_probed)
        monkeypatch.setattr("app.features.streaming.library.ffprobe.ffprobe_bin", lambda: None)

        st = StatusTracker(**mock_config)
        st.download_dir = str(tmp_path)
        status = {"id": "test-id", "status": "finished", "final_name": str(test_file)}

        await st.process_status_update(status)

        assert st.info.filename == "test.mp4", "filename must still be finalized"
        assert st.info.extras["is_video"] is True, "media flags must fall back to True when ffprobe is missing"
        assert st.info.extras["is_audio"] is True, "media flags must fall back to True when ffprobe is missing"
        assert "media_profile" not in st.info.extras, "media_profile requires probe data"

    @pytest.mark.asyncio
    async def test_queue_processes_remaining_updates(self, mock_config: dict[str, Any]) -> None:
        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 100})
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 200})
        queue.put(Terminator())

        config: dict[str, Any] = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=10)
        assert st.info.downloaded_bytes == 200, "Should process all queued updates"

    @pytest.mark.asyncio
    async def test_queue_stops_final_update(self, tmp_path: Path, mock_config: dict[str, Any]) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")

        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "finished", "final_name": str(test_file)})
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 999})

        config: dict[str, Any] = {**mock_config, "status_queue": queue, "download_dir": str(tmp_path)}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=10)
        assert st.final_update is True, "Should stop draining after final update"

    @pytest.mark.asyncio
    async def test_drain_queue_skips_invalid(self, mock_config: dict[str, Any]) -> None:
        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "downloading"})
        queue.put(None)

        config: dict[str, Any] = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=5)
        assert st.info.status == "downloading", "valid updates should still be processed"

    def test_cancel_update_task(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        st.update_task = Mock()
        st.update_task.done = Mock(return_value=False)
        st.update_task.cancel = Mock()

        st.cancel_update_task()
        st.update_task.cancel.assert_called_once()

    def test_cancel_update_task_noop(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)

        st.cancel_update_task()
        assert st.update_task is None, "missing tasks should be ignored"

    def test_put_terminator_adds_queue(self, mock_config: dict[str, Any]) -> None:
        queue = DummyQueue()
        config: dict[str, Any] = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        st.put_terminator()
        assert 1 == len(queue.items), "Should add terminator to queue"
        assert isinstance(queue.items[0], Terminator), "Should add Terminator instance"

    @pytest.mark.asyncio
    async def test_progress_emits_item_progress(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        st.info.status = "downloading"
        calls: list = []
        st._notify = Mock()
        st._notify.emit = Mock(side_effect=lambda *a, **kw: calls.append((a, kw)))

        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}
        )

        progress_calls = [c for c in calls if c[0][0] == Events.ITEM_PROGRESS]
        updated_calls = [c for c in calls if c[0][0] == Events.ITEM_UPDATED]
        assert len(progress_calls) == 1
        assert len(updated_calls) == 0
        payload = progress_calls[0][1]["data"]
        assert payload["_id"] == st.info._id
        assert payload["percent"] == 50.0
        assert "options" not in payload

    @pytest.mark.asyncio
    async def test_change_emits_item_updated(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        st.info.status = "started"
        calls: list = []
        st._notify = Mock()
        st._notify.emit = Mock(side_effect=lambda *a, **kw: calls.append((a, kw)))

        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 10, "total_bytes": 100}
        )

        updated_calls = [c for c in calls if c[0][0] == Events.ITEM_UPDATED]
        assert len(updated_calls) == 1
        assert updated_calls[0][1]["data"] is st.info

    @pytest.mark.asyncio
    async def test_progress_throttled(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        st.info.status = "downloading"
        st._progress_interval = 0.5
        calls: list = []
        st._notify = Mock()
        st._notify.emit = Mock(side_effect=lambda *a, **kw: calls.append((a, kw)))

        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 10, "total_bytes": 100}
        )
        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 20, "total_bytes": 100}
        )
        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 30, "total_bytes": 100}
        )

        progress_calls = [c for c in calls if c[0][0] == Events.ITEM_PROGRESS]
        assert len(progress_calls) == 1, "Rapid ticks should be throttled to one emission"
        assert st._pending_progress is True

    @pytest.mark.asyncio
    async def test_flush_on_status_change(self, mock_config: dict[str, Any]) -> None:
        st = StatusTracker(**mock_config)
        st.info.status = "downloading"
        st._progress_interval = 10.0
        calls: list = []
        st._notify = Mock()
        st._notify.emit = Mock(side_effect=lambda *a, **kw: calls.append((a, kw)))

        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 10, "total_bytes": 100}
        )
        await st.process_status_update(
            {"id": "test-id", "status": "downloading", "downloaded_bytes": 50, "total_bytes": 100}
        )

        assert st._pending_progress is True

        await st.process_status_update({"id": "test-id", "status": "error", "error": "fail"})

        progress_calls = [c for c in calls if c[0][0] == Events.ITEM_PROGRESS]
        updated_calls = [c for c in calls if c[0][0] == Events.ITEM_UPDATED]
        assert len(progress_calls) == 2, "Pending progress should be flushed before status change"
        assert len(updated_calls) == 1
        assert st._pending_progress is False


class TestQueueManager:
    def test_attach_schedules_retries(self) -> None:
        from app.features.downloads.runtime.monitors import check_retries

        queue: Any = object.__new__(DownloadQueue)
        queue.config = SimpleNamespace(retry=2, auto_clear_history_days=0)
        queue._notify = Mock()

        with (
            patch("app.features.downloads.runtime.queue_manager.Scheduler") as scheduler,
            patch("app.features.downloads.runtime.queue_manager.Services"),
        ):
            queue.attach(Mock())

        jobs = [call.kwargs["id"] for call in scheduler.get_instance.return_value.add.call_args_list]
        assert check_retries.__name__ in jobs

    class LiveStore:
        def __init__(self, items: dict[str, Download]) -> None:
            self._items = items

        def items(self):
            return self._items.items()

        def __contains__(self, key: str) -> bool:
            return key in self._items

        def __len__(self) -> int:
            return len(self._items)

    @staticmethod
    def _video_queue() -> Mock:
        async def put(item):
            return item

        queue_manager = Mock()
        queue_manager.config = Mock(
            download_path="/tmp",
            temp_path="/tmp",
            output_template="%(title)s.%(ext)s",
            output_template_chapter="%(title)s.%(ext)s",
            prevent_live_premiere=False,
        )
        queue_manager.done.get = AsyncMock(side_effect=KeyError)
        queue_manager.queue.get = AsyncMock(side_effect=KeyError)
        queue_manager.done.put = AsyncMock(side_effect=put)
        queue_manager.queue.put = AsyncMock(side_effect=put)
        queue_manager.pool.trigger_download = Mock()
        queue_manager._notify.emit = Mock()
        return queue_manager

    @staticmethod
    def _video_item() -> SimpleNamespace:
        return SimpleNamespace(
            extras={},
            folder="",
            preset="default",
            cookies="",
            template="",
            cli=[],
            auto_start=True,
            force_start=False,
        )

    @staticmethod
    def _any_video_item() -> Any:
        return TestQueueManager._video_item()

    def test_queue_caps_visible_items(self) -> None:
        queue_manager: Any = object.__new__(DownloadQueue)
        items: dict[str, Any] = {f"id{i}": Mock(info=make_item(id=f"id{i}", title=f"Video {i}")) for i in range(5)}
        queue_manager.queue = self.LiveStore(items)
        queue_manager.pool = Mock()
        queue_manager.pool.get_active_downloads.return_value = {}

        snapshot = DownloadQueue.live_queue(queue_manager, limit=2)

        queue_view = snapshot["queue"]
        assert isinstance(queue_view, dict)
        assert list(queue_view.keys()) == ["id0", "id1"]
        assert snapshot["queue_count"] == 5
        assert snapshot["queue_loaded"] == 2
        assert snapshot["queue_limit"] == 2

    def test_live_queue_keeps_active(self) -> None:
        queue_manager: Any = object.__new__(DownloadQueue)
        items: dict[str, Any] = {f"id{i}": Mock(info=make_item(id=f"id{i}", title=f"Video {i}")) for i in range(5)}
        queue_manager.queue = self.LiveStore(items)
        queue_manager.pool = Mock()
        queue_manager.pool.get_active_downloads.return_value = {
            "id3": Mock(info=make_item(id="id3", title="Active 3")),
            "id4": Mock(info=make_item(id="id4", title="Active 4")),
        }

        snapshot = DownloadQueue.live_queue(queue_manager, limit=1)

        queue_view = snapshot["queue"]
        assert isinstance(queue_view, dict)
        assert list(queue_view.keys()) == ["id3", "id4"]
        assert snapshot["queue_count"] == 5
        assert snapshot["queue_loaded"] == 2
        assert snapshot["queue_limit"] == 1

    @pytest.mark.asyncio
    async def test_live_reextracts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[dict | None] = []

        def fake_download(*, info, info_dict, logs):
            seen.append(info_dict)
            return SimpleNamespace(info=info, info_dict=info_dict, logs=logs)

        monkeypatch.setattr("app.features.downloads.runtime.video_processor.Download", fake_download)

        result = await add_video(
            queue=self._video_queue(),
            item=self._any_video_item(),
            entry={
                "id": "live-id",
                "title": "Live stream",
                "webpage_url": "https://example.test/live",
                "is_live": True,
                "live_status": "is_live",
                "_ytptube_reextract": True,
            },
        )

        assert result == {"status": "ok"}
        assert seen == [None]

    @pytest.mark.asyncio
    async def test_regular_reuses_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[dict | None] = []

        def fake_download(*, info, info_dict, logs):
            seen.append(info_dict)
            return SimpleNamespace(info=info, info_dict=info_dict, logs=logs)

        monkeypatch.setattr("app.features.downloads.runtime.video_processor.Download", fake_download)

        entry = {
            "id": "video-id",
            "title": "Video",
            "webpage_url": "https://example.test/video",
            "live_status": "not_live",
            "formats": [{"format_id": "18"}],
        }

        result = await add_video(queue=self._video_queue(), item=self._any_video_item(), entry=entry)

        assert result == {"status": "ok"}
        assert seen == [entry]

    @pytest.mark.asyncio
    async def test_transparent_reextracts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen_info: list[dict | None] = []
        seen_url: list[str] = []

        def fake_download(*, info, info_dict, logs):  # noqa: ARG001
            seen_info.append(info_dict)
            seen_url.append(info.url)
            return SimpleNamespace(info=info, info_dict=info_dict, logs=logs)

        monkeypatch.setattr("app.features.downloads.runtime.video_processor.Download", fake_download)

        entry = {
            "_type": "url_transparent",
            "ie_key": "VHXEmbed",
            "id": "738153",
            "title": "Yes or No",
            "url": "https://embed.vhx.tv/videos/738153?auth-user-token=short-lived",
            "webpage_url": "https://watch.dropout.tv/game-changer/season:2/videos/yes-or-no",
            "series": "Game Changer",
            "season_number": 2,
            "episode_number": 6,
            "episode": "Yes or No",
        }

        result = await add_video(queue=self._video_queue(), item=self._any_video_item(), entry=entry)

        assert result == {"status": "ok"}
        assert seen_info == [None]
        assert seen_url == ["https://watch.dropout.tv/game-changer/season:2/videos/yes-or-no"]

    @pytest.mark.asyncio
    async def test_transparent_add_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.downloads.runtime import item_adder

        seen: list[tuple[dict, Any, list[str] | None]] = []

        async def fake_add_video(*, queue, entry, item, logs):  # noqa: ARG001
            seen.append((entry, item, logs))
            return {"status": "ok"}

        monkeypatch.setattr(item_adder, "add_video", fake_add_video)

        item = Item(url="https://watch.dropout.tv/game-changer/season:2/videos/yes-or-no", preset="default")
        entry = {
            "_type": "url_transparent",
            "ie_key": "VHXEmbed",
            "title": "Yes or No",
            "url": "https://embed.vhx.tv/videos/738153?auth-user-token=short-lived",
            "webpage_url": item.url,
            "series": "Game Changer",
            "season_number": 2,
            "episode_number": 6,
            "episode": "Yes or No",
        }

        result = await item_adder.add_item(queue=self._video_queue(), entry=entry, item=item, logs=["log"])

        assert result == {"status": "ok"}
        assert seen == [(entry, item, ["log"])]

    def test_extract_no_subs(self) -> None:
        from app.features.downloads.runtime.item_adder import _extract_config

        config = {
            "format": "bv*+ba/b",
            "sleep_interval_requests": 3.0,
            "sleep_interval_subtitles": 76.0,
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": ["en.*", "fr.*"],
            "postprocessors": [
                {"key": "FFmpegSubtitlesConvertor", "format": "srt", "when": "before_dl"},
                {"key": "FFmpegMetadata"},
            ],
        }

        stripped, changed = _extract_config(config)

        assert changed is True
        assert stripped["format"] == "bv*+ba/b"
        assert stripped["sleep_interval_requests"] == 3.0
        assert stripped["sleep_interval_subtitles"] == 76.0
        assert "writeautomaticsub" not in stripped
        assert "writesubtitles" not in stripped
        assert "subtitleslangs" not in stripped
        assert stripped["postprocessors"] == [{"key": "FFmpegMetadata"}]

    @pytest.mark.asyncio
    async def test_light_reextracts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.downloads.runtime.video_processor import LIGHT_EXTRACT_KEY

        seen: list[dict | None] = []

        def fake_download(*, info, info_dict, logs):
            seen.append(info_dict)
            return SimpleNamespace(info=info, info_dict=info_dict, logs=logs)

        monkeypatch.setattr("app.features.downloads.runtime.video_processor.Download", fake_download)

        entry = {
            "id": "video-id",
            "title": "Video",
            "webpage_url": "https://example.test/video",
            "live_status": "not_live",
            "formats": [{"format_id": "18"}],
            LIGHT_EXTRACT_KEY: True,
        }

        result = await add_video(queue=self._video_queue(), item=self._any_video_item(), entry=entry)

        assert result == {"status": "ok"}
        assert seen == [None]

    @pytest.mark.asyncio
    async def test_yt_no_subs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.downloads.runtime import item_adder
        from app.features.downloads.runtime.video_processor import LIGHT_EXTRACT_KEY

        seen_config: list[dict] = []
        seen_entry: list[dict] = []

        async def fake_fetch_info(*, config, **kwargs):  # noqa: ARG001
            seen_config.append(config)
            return ({"id": "video-id", "title": "Video", "_type": "video", "formats": [{"format_id": "18"}]}, [])

        async def fake_add_video(*, queue, entry, item, logs):  # noqa: ARG001
            seen_entry.append(entry)
            return {"status": "ok"}

        class Opts:
            def get_all(self):
                return {
                    "format": "bv*+ba/b",
                    "sleep_interval_requests": 3.0,
                    "writeautomaticsub": True,
                    "writesubtitles": True,
                    "subtitleslangs": ["en.*", "fr.*"],
                }

        item = Item(
            url="https://www.youtube.com/watch?v=video-id",
            preset="default",
            folder="",
            cookies="",
            template="",
            extras={},
            auto_start=True,
            requeued=False,
        )
        monkeypatch.setattr(item, "get_ytdlp_opts", lambda: Opts())
        monkeypatch.setattr(item, "get_archive_id", lambda: None)
        monkeypatch.setattr(item, "is_archived", lambda: False)
        monkeypatch.setattr(item, "get_archive_file", lambda: None)
        monkeypatch.setattr(item, "get_extractor", lambda: "Youtube")
        queue = self._video_queue()
        queue.config.ytdlp_debug = False
        queue.config.ignore_archived_items = False

        monkeypatch.setattr(item_adder, "fetch_info", fake_fetch_info)
        monkeypatch.setattr(item_adder, "add_video", fake_add_video)
        monkeypatch.setattr(
            item_adder.Conditions,
            "get_instance",
            classmethod(lambda cls: SimpleNamespace(match=AsyncMock(return_value=None))),
        )

        result = await item_adder.add(queue=queue, item=item)

        assert result == {"status": "ok"}
        assert seen_config == [{"format": "bv*+ba/b", "sleep_interval_requests": 3.0}]
        assert seen_entry[0][LIGHT_EXTRACT_KEY] is True

    @pytest.mark.asyncio
    async def test_yt_url_no_subs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.downloads.runtime import item_adder
        from app.features.downloads.runtime.video_processor import LIGHT_EXTRACT_KEY

        seen_config: list[dict] = []
        seen_entry: list[dict] = []

        async def fake_fetch_info(*, config, **kwargs):  # noqa: ARG001
            seen_config.append(config)
            return ({"id": "video-id", "title": "Video", "_type": "video", "formats": [{"format_id": "18"}]}, [])

        async def fake_add_video(*, queue, entry, item, logs):  # noqa: ARG001
            seen_entry.append(entry)
            return {"status": "ok"}

        class Opts:
            def get_all(self):
                return {"format": "bv*+ba/b", "writeautomaticsub": True, "subtitleslangs": ["fr.*"]}

        item = Item(url="https://youtu.be/video-id", preset="default")
        monkeypatch.setattr(item, "get_ytdlp_opts", lambda: Opts())
        monkeypatch.setattr(item, "get_archive_id", lambda: None)
        monkeypatch.setattr(item, "is_archived", lambda: False)
        monkeypatch.setattr(item, "get_archive_file", lambda: None)
        monkeypatch.setattr(item, "get_extractor", lambda: None)
        queue = self._video_queue()
        queue.config.ytdlp_debug = False
        queue.config.ignore_archived_items = False

        monkeypatch.setattr(item_adder, "fetch_info", fake_fetch_info)
        monkeypatch.setattr(item_adder, "add_video", fake_add_video)
        monkeypatch.setattr(
            item_adder.Conditions,
            "get_instance",
            classmethod(lambda cls: SimpleNamespace(match=AsyncMock(return_value=None))),
        )

        result = await item_adder.add(queue=queue, item=item)

        assert result == {"status": "ok"}
        assert seen_config == [{"format": "bv*+ba/b"}]
        assert seen_entry[0][LIGHT_EXTRACT_KEY] is True

    @pytest.mark.asyncio
    async def test_non_yt_keeps_subs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.features.downloads.runtime import item_adder
        from app.features.downloads.runtime.video_processor import LIGHT_EXTRACT_KEY

        seen_config: list[dict] = []
        seen_entry: list[dict] = []

        async def fake_fetch_info(*, config, **kwargs):  # noqa: ARG001
            seen_config.append(config)
            return ({"id": "video-id", "title": "Video", "_type": "video", "formats": [{"format_id": "18"}]}, [])

        async def fake_add_video(*, queue, entry, item, logs):  # noqa: ARG001
            seen_entry.append(entry)
            return {"status": "ok"}

        class Opts:
            def get_all(self):
                return {
                    "format": "bv*+ba/b",
                    "writeautomaticsub": True,
                    "subtitleslangs": ["fr.*"],
                }

        item = Item(url="https://example.test/video", preset="default")
        monkeypatch.setattr(item, "get_ytdlp_opts", lambda: Opts())
        monkeypatch.setattr(item, "get_archive_id", lambda: None)
        monkeypatch.setattr(item, "is_archived", lambda: False)
        monkeypatch.setattr(item, "get_archive_file", lambda: None)
        monkeypatch.setattr(item, "get_extractor", lambda: "Generic")
        queue = self._video_queue()
        queue.config.ytdlp_debug = False
        queue.config.ignore_archived_items = False

        monkeypatch.setattr(item_adder, "fetch_info", fake_fetch_info)
        monkeypatch.setattr(item_adder, "add_video", fake_add_video)
        monkeypatch.setattr(
            item_adder.Conditions,
            "get_instance",
            classmethod(lambda cls: SimpleNamespace(match=AsyncMock(return_value=None))),
        )

        result = await item_adder.add(queue=queue, item=item)

        assert result == {"status": "ok"}
        assert seen_config == [{"format": "bv*+ba/b", "writeautomaticsub": True, "subtitleslangs": ["fr.*"]}]
        assert LIGHT_EXTRACT_KEY not in seen_entry[0]

    @pytest.mark.asyncio
    async def test_cleanup_thumbnails(self, tmp_path: Path) -> None:
        from app.features.downloads.runtime.monitors import cleanup_thumbnails

        queue_manager: Any = object.__new__(DownloadQueue)
        queue_manager.config = SimpleNamespace(temp_path=str(tmp_path), thumb_sidecar=False)
        queue_manager.done = Mock()

        cache_root = tmp_path / "thumbnails"
        cache_root.mkdir(parents=True, exist_ok=True)
        keep = cache_root / "keep-id.jpg"
        drop = cache_root / "drop-id.jpg"
        keep.write_text("keep")
        drop.write_text("drop")

        queue_manager.done.get_by_id = AsyncMock(side_effect=lambda item_id: item_id == "keep-id")

        await cleanup_thumbnails(queue_manager)

        assert keep.exists()
        assert not drop.exists()

    @pytest.mark.asyncio
    async def test_live_item_defers_close(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.queue = Mock()
        queue_manager.done = Mock()
        queue_manager._notify = Mock()

        item = Mock()
        item.info = make_item(id="queued-id")
        item.is_live = True
        item.running.return_value = True
        item.cancel.return_value = True
        item.close = AsyncMock()

        queue_manager.queue.get = AsyncMock(return_value=item)

        status = await DownloadQueue.cancel(queue_manager, [item.info._id])

        item.cancel.assert_called_once()
        item.close.assert_not_awaited()
        assert status[item.info._id] == "ok", "Running cancel should still report success"

    @pytest.mark.asyncio
    async def test_cancel_regular_closes(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.queue = Mock()
        queue_manager.done = Mock()
        queue_manager._notify = Mock()

        item = Mock()
        item.info = make_item(id="queued-id")
        item.is_live = False
        item.running.return_value = True
        item.cancel.return_value = True
        item.close = AsyncMock()

        queue_manager.queue.get = AsyncMock(return_value=item)

        status = await DownloadQueue.cancel(queue_manager, [item.info._id])

        item.cancel.assert_called_once()
        item.close.assert_awaited_once()
        assert status[item.info._id] == "ok", "Regular running cancel should still report success"

    @pytest.mark.asyncio
    async def test_clear_flushes_history(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.config = Mock(remove_files=False, download_path="/tmp")
        queue_manager._notify = Mock()

        item = Mock()
        item.info = make_item(id="done-id", title="Finished clip")
        item.info._id = "done-id"
        item.info.status = "finished"
        item.info.filename = "clip.mp4"
        item.info.folder = ""

        done_store = Mock()
        done_store.get = AsyncMock(return_value=item)
        done_store.delete = AsyncMock()
        done_store.flush = AsyncMock()
        queue_manager.done = done_store

        status = await DownloadQueue.clear(queue_manager, [item.info._id], remove_file=False)

        done_store.delete.assert_awaited_once_with(item.info._id)
        done_store.flush.assert_awaited_once()
        assert status[item.info._id] == "ok", "Clear should still report success after flushing deletes"

    @pytest.mark.asyncio
    async def test_clear_bulk_notifies(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.config = Mock(remove_files=False, download_path="/tmp")
        queue_manager._notify = Mock()

        item_one = Mock()
        item_one.info = make_item(id="done-id-1", title="Finished clip 1")
        item_one.info._id = "done-id-1"
        item_one.info.status = "finished"

        item_two = Mock()
        item_two.info = make_item(id="done-id-2", title="Finished clip 2")
        item_two.info._id = "done-id-2"
        item_two.info.status = "finished"

        done_store = Mock()
        done_store.get_many_by_ids = AsyncMock(return_value=[("done-id-1", item_one), ("done-id-2", item_two)])
        done_store.bulk_delete = AsyncMock(return_value=2)
        queue_manager.done = done_store

        result = await DownloadQueue.clear_bulk(queue_manager, ["done-id-1", "done-id-2"], remove_file=False)

        assert result == {"deleted": 2}
        done_store.get_many_by_ids.assert_awaited_once_with(["done-id-1", "done-id-2"])
        done_store.bulk_delete.assert_awaited_once_with(["done-id-1", "done-id-2"])
        queue_manager._notify.emit.assert_called_once()
        assert queue_manager._notify.emit.call_args.args[0] == Events.ITEM_BULK_DELETED
        assert queue_manager._notify.emit.call_args.kwargs["data"]["count"] == 2
        assert queue_manager._notify.emit.call_args.kwargs["data"]["removed_files"] == 0
        assert len(queue_manager._notify.emit.call_args.kwargs["data"]["items"]) == 2
        assert queue_manager._notify.emit.call_args.kwargs["data"]["items"][0]["id"] == "done-id-1"
        assert queue_manager._notify.emit.call_args.kwargs["data"]["items"][1]["id"] == "done-id-2"

    @pytest.mark.asyncio
    async def test_clear_status_fetches(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.config = Mock(remove_files=False, download_path="/tmp")
        queue_manager._notify = Mock()

        item = Mock()
        item.info = make_item(id="done-id", title="Cleared clip")

        done_store = Mock()
        done_store.bulk_delete_by_status = AsyncMock(return_value=1)
        done_store.get_many_by_status = AsyncMock(return_value=[("done-id", item)])
        queue_manager.done = done_store

        result = await DownloadQueue.clear_by_status(queue_manager, "finished", remove_file=False)

        assert result == {"deleted": 1}
        done_store.get_many_by_status.assert_awaited_once_with("finished")
        done_store.bulk_delete_by_status.assert_awaited_once_with("finished")
        queue_manager._notify.emit.assert_called_once()
        assert queue_manager._notify.emit.call_args.args[0] == Events.ITEM_BULK_DELETED
        assert queue_manager._notify.emit.call_args.kwargs["data"]["count"] == 1
        assert queue_manager._notify.emit.call_args.kwargs["data"]["status"] == "finished"
        assert len(queue_manager._notify.emit.call_args.kwargs["data"]["items"]) == 1
        assert queue_manager._notify.emit.call_args.kwargs["data"]["items"][0]["id"] == "done-id"

    @pytest.mark.asyncio
    async def test_clear_status_files_fetch(self) -> None:
        queue_manager = object.__new__(DownloadQueue)
        queue_manager.config = Mock(remove_files=True, download_path="/tmp")
        queue_manager._notify = Mock()

        item = Mock()
        item.info = make_item(id="done-id", title="Finished clip")
        item.info._id = "done-id"
        item.info.status = "finished"

        done_store = Mock()
        done_store.get_many_by_status = AsyncMock(return_value=[("done-id", item)])
        queue_manager.done = done_store
        queue_manager.clear_bulk = AsyncMock(return_value={"deleted": 1})

        result = await DownloadQueue.clear_by_status(queue_manager, "finished", remove_file=True)

        assert result == {"deleted": 1}
        done_store.get_many_by_status.assert_awaited_once_with("finished")
        queue_manager.clear_bulk.assert_awaited_once_with(["done-id"], remove_file=True)


class TestPoolManager:
    @pytest.mark.asyncio
    async def test_cancelled_file_stays_finished(self, monkeypatch: pytest.MonkeyPatch) -> None:
        emitted_events: list[str] = []

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(event, **_kwargs):
                emitted_events.append(event)

        monkeypatch.setattr("app.features.downloads.runtime.pool_manager.EventBus", EB)

        queue_store = Mock()
        queue_store.exists = AsyncMock(return_value=True)
        queue_store.delete = AsyncMock()
        done_store = Mock()
        done_store.put = AsyncMock()
        queue = Mock(queue=queue_store, done=done_store)
        config = Mock(max_workers=1, max_workers_per_extractor=1, download_path="/tmp")
        pool = PoolManager(queue=queue, config=config)

        info = make_item(id="done-id", title="Live clip")
        info.status = "finished"
        info.filename = "live.mp4"
        info.is_archivable = False
        info.is_archived = False

        entry = Mock()
        entry.id = info._id
        entry.is_live = True
        entry.info = info
        entry.start = AsyncMock()
        entry.close = AsyncMock()
        entry.is_cancelled.return_value = True

        await pool._download_file(info._id, entry)

        assert info.status == "finished", "Finished live downloads should not be rewritten to cancelled"
        assert Events.ITEM_COMPLETED in emitted_events, "Completed event should be emitted for finalized file"
        assert Events.ITEM_CANCELLED not in emitted_events, "Cancelled event should not be emitted once finalized"
        done_store.put.assert_awaited_once_with(entry)

    @pytest.mark.asyncio
    async def test_cancelled_regular_file_stays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        emitted_events: list[str] = []

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(event, **_kwargs):
                emitted_events.append(event)

        monkeypatch.setattr("app.features.downloads.runtime.pool_manager.EventBus", EB)

        queue_store = Mock()
        queue_store.exists = AsyncMock(return_value=True)
        queue_store.delete = AsyncMock()
        done_store = Mock()
        done_store.put = AsyncMock()
        queue = Mock(queue=queue_store, done=done_store)
        config = Mock(max_workers=1, max_workers_per_extractor=1, download_path="/tmp")
        pool = PoolManager(queue=queue, config=config)

        info = make_item(id="done-id", title="Regular clip")
        info.status = "finished"
        info.filename = "video.mp4"
        info.is_archivable = False
        info.is_archived = False

        entry = Mock()
        entry.id = info._id
        entry.is_live = False
        entry.info = info
        entry.start = AsyncMock()
        entry.close = AsyncMock()
        entry.is_cancelled.return_value = True

        await pool._download_file(info._id, entry)

        assert info.status == "cancelled", "Regular cancelled downloads should keep cancelled status"
        assert Events.ITEM_CANCELLED in emitted_events, "Cancelled event should be emitted for regular downloads"
        assert Events.ITEM_COMPLETED not in emitted_events, (
            "Completed event should remain live-only for cancel finalization"
        )
        done_store.put.assert_awaited_once_with(entry)
