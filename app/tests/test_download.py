import logging
import os
import signal
from multiprocessing.reduction import ForkingPickler
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.library.Events import EventBus, Events
from app.library.downloads import Download, NestedLogger, Terminator
from app.library.downloads.hooks import HookHandlers
from app.library.downloads.pool_manager import PoolManager
from app.library.downloads.process_manager import ProcessManager
from app.library.downloads.queue_manager import DownloadQueue
from app.library.downloads.status_tracker import StatusTracker
from app.library.downloads.temp_manager import TempManager
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

    def get(self, timeout: float | None = None) -> Any:
        if not self.items:
            return None
        return self.items.pop(0)


class TestNestedLogger:
    def test_debug_maps_levels_and_strips_prefix(self) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.downloads.core.EventBus", EB)

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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.downloads.core.EventBus", EB)

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
    async def test_started_time_is_set_in_main_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
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


class TestDownloadFlow:
    def test_download_pushes_download_skipped_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        download = Download(
            info=make_item(),
            info_dict={"id": "test-id", "url": "http://u", "formats": [{"format_id": "18"}]},
        )
        download.status_queue = cast(Any, DummyQueue())
        download._hook_handlers = Mock(
            progress_hook=Mock(),
            postprocessor_hook=Mock(),
            post_hook=Mock(),
        )
        download.info.get_ytdlp_opts = Mock(
            return_value=Mock(
                add=Mock(
                    return_value=Mock(
                        get_all=Mock(return_value={"skip_download": True}),
                    )
                )
            )
        )

        class FakeYTDLP:
            def __init__(self, params):
                self.params = params
                self._download_retcode = 0
                self._interrupted = False

            def process_ie_result(self, ie_result, download):
                return ie_result, download

        monkeypatch.setattr("app.library.downloads.core.YTDLP", FakeYTDLP)

        download._download()

        queue = cast(DummyQueue, download.status_queue)
        assert queue.items[0]["download_skipped"] is True
        assert queue.items[1]["download_skipped"] is True

    def test_download_resets_sigint_handler_in_worker(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        item = make_item(id="live-id")
        item.is_live = True
        download = Download(
            info=item,
            info_dict={"id": "live-id", "url": "http://u", "formats": [{"format_id": "18"}]},
        )
        download._process_manager.cancel_event = Mock(wait=Mock())
        download.status_queue = cast(Any, DummyQueue())
        download._hook_handlers = Mock(
            progress_hook=Mock(),
            postprocessor_hook=Mock(),
            post_hook=Mock(),
        )
        download.info.get_ytdlp_opts = Mock(
            return_value=Mock(add=Mock(return_value=Mock(get_all=Mock(return_value={}))))
        )

        created_ydl: list[Any] = []

        class FakeYTDLP:
            def __init__(self, params):
                self.params = params
                self._download_retcode = 0
                self._interrupted = False
                self.to_screen = Mock()
                created_ydl.append(self)

            def process_ie_result(self, ie_result, download):
                return ie_result, download

            def download(self, url_list):
                return 0

        signal_mock = Mock()
        thread_instances: list[Mock] = []

        def build_thread(*_args, **_kwargs):
            thread = Mock(start=Mock())
            thread_instances.append(thread)
            return thread

        thread_mock = Mock(side_effect=build_thread)
        monkeypatch.setattr("app.library.downloads.core.YTDLP", FakeYTDLP)
        monkeypatch.setattr("app.library.downloads.core.signal.signal", signal_mock)
        monkeypatch.setattr("app.library.downloads.core.threading.Thread", thread_mock)

        download._download()

        signal_mock.assert_any_call(signal.SIGINT, signal.default_int_handler)

        live_cancel_thread = next(
            call for call in thread_mock.call_args_list if call.kwargs.get("name", "").startswith("cancel-watch-")
        )
        live_cancel_thread_index = thread_mock.call_args_list.index(live_cancel_thread)
        thread_instances[live_cancel_thread_index].start.assert_called_once()
        target = live_cancel_thread.kwargs["target"]
        ydl = created_ydl[0]

        if "posix" == os.name:
            with (
                patch("app.library.downloads.core.os.getpid", return_value=12345),
                patch("app.library.downloads.core.os.kill") as mock_kill,
            ):
                target()
                mock_kill.assert_called_once_with(12345, signal.SIGINT)
        else:
            with patch("app.library.downloads.core._thread.interrupt_main") as mock_interrupt_main:
                target()
                mock_interrupt_main.assert_called_once_with()

        assert ydl._interrupted is True
        ydl.to_screen.assert_called_once_with("[info] Interrupt received, exiting cleanly...")

    def test_download_prefers_real_playlist_extras_over_placeholder_preinfo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

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
        download.info.get_ytdlp_opts = Mock(
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

        monkeypatch.setattr("app.library.downloads.core.YTDLP", FakeYTDLP)

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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.downloads.core.EventBus", EB)

        item = ItemDTO(
            id="id1",
            title="T",
            url="http://u",
            folder="f",
            download_dir=str(tmp_path),
            temp_dir=str(tmp_path),
        )
        download = Download(info=item)

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
                    "final_name": str(tmp_path / "video.mp4"),
                }
            )
            queue.put(Terminator())

        download._download = fake_download

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

    @pytest.mark.asyncio
    async def test_live_cancelled_download_drains_final_status_updates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.downloads.core.EventBus", EB)

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
        final_file = tmp_path / "live.mp4"
        final_file.write_text("test content")

        def fake_download():
            queue = cast(Any, download.status_queue)
            queue.put({"id": download.id, "status": "downloading", "downloaded_bytes": 10})
            queue.put({"id": download.id, "status": "finished", "final_name": str(final_file)})
            queue.put(Terminator())

        download._download = fake_download

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
    async def test_regular_cancelled_download_skips_live_drain_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(*_args, **_kwargs):
                return None

        monkeypatch.setattr("app.library.downloads.core.EventBus", EB)

        tracker = Mock()
        tracker.final_update = False
        tracker.drain_queue = AsyncMock()

        async def progress_update():
            return None

        tracker.progress_update = progress_update

        monkeypatch.setattr("app.library.downloads.core.StatusTracker", Mock(return_value=tracker))
        monkeypatch.setattr("app.library.downloads.core.HookHandlers", Mock())

        download = Download(make_item(id="regular-id"))

        mock_proc = Mock()
        mock_proc.join = Mock(return_value=0)

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

    def test_spawn_pickling_ignores_local_event_listener(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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

        monkeypatch.setattr("app.library.downloads.core.Config", Cfg)

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


class TestTempManager:
    def test_create_temp_path_when_disabled(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, "/tmp", temp_disabled=True, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is None, "Should return None when temp_disabled is True"
        assert tm.temp_path is None, "temp_path should remain None when disabled"

    def test_create_temp_path_when_no_temp_dir(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, None, temp_disabled=False, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is None, "Should return None when temp_dir is None"
        assert tm.temp_path is None, "temp_path should remain None when no temp_dir"

    def test_create_temp_path_creates_directory(self, tmp_path: Path) -> None:
        info = make_item(id="test123")
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)

        result = tm.create_temp_path()
        assert result is not None, "Should return Path when enabled"
        assert result.exists(), "Temporary directory should be created"
        assert result.parent == tmp_path, "Temp directory should be created in temp_dir"
        assert tm.temp_path == result, "temp_path should be set to created path"

    def test_create_temp_path_uses_consistent_hash(self, tmp_path: Path) -> None:
        info = make_item(id="test123")
        logger = logging.getLogger("test")
        tm1 = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)
        tm2 = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=False, logger=logger)

        path1 = tm1.create_temp_path()
        path2 = tm2.create_temp_path()
        assert path1 == path2, "Same download ID should produce same temp path"

    def test_delete_temp_when_disabled(self, tmp_path: Path) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=True, temp_keep=False, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should not delete when temp_disabled is True"

    def test_delete_temp_when_temp_keep_enabled(self, tmp_path: Path) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, str(tmp_path), temp_disabled=False, temp_keep=True, logger=logger)
        tm.temp_path = tmp_path / "test"
        tm.temp_path.mkdir()

        tm.delete_temp()
        assert tm.temp_path.exists(), "Should not delete when temp_keep is True"

    def test_delete_temp_when_no_temp_path(self) -> None:
        info = make_item()
        logger = logging.getLogger("test")
        tm = TempManager(info, "/tmp", temp_disabled=False, temp_keep=False, logger=logger)

        tm.delete_temp()

    def test_delete_temp_keeps_partial_download(self, tmp_path: Path) -> None:
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

    def test_delete_temp_refuses_to_delete_temp_root(self, tmp_path: Path) -> None:
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

    def test_started_returns_true_when_process_created(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        assert pm.started() is False, "Should return False when no process created"

        pm.create_process(lambda: None)
        assert pm.started() is True, "Should return True after process created"

    def test_running_returns_false_when_no_process(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        assert pm.running() is False, "Should return False when no process"

    def test_is_cancelled_returns_false_by_default(self) -> None:
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

    def test_cancel_returns_false_when_not_started(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = pm.cancel()
        assert result is False, "Should return False when process not started"
        assert pm.is_cancelled() is False, "Should not mark as cancelled when not started"

    def test_kill_returns_false_when_not_running(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = pm.kill()
        assert result is False, "Should return False when process not running"

    def test_kill_sends_sigusr1_on_posix(self) -> None:
        if "posix" != os.name:
            pytest.skip("Test only runs on POSIX systems")

        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.proc.pid = 12345
        pm.proc.ident = 67890
        pm.proc.is_alive = Mock(side_effect=[True, False, False])

        with patch("app.library.downloads.process_manager.os.kill") as mock_kill:
            result = pm.kill()
            mock_kill.assert_called_once_with(12345, signal.SIGUSR1)
            assert result is True, "Should return True when process killed successfully"

    def test_kill_uses_live_cancel_event_and_longer_graceful_timeout(self) -> None:
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
            patch("app.library.downloads.process_manager.os.kill") as mock_kill,
            patch(
                "app.library.downloads.process_manager.wait_for_process_with_timeout", return_value=True
            ) as mock_wait,
        ):
            assert pm_live.kill() is True, "Live downloads should stop via the shared cancel event"
            assert pm_live.cancel_event.is_set() is True, "Live kill should signal the worker cancel event"
            mock_kill.assert_not_called()
            mock_wait.assert_called_once_with(pm_live.proc, 10)

        if "posix" != os.name:
            pytest.skip("Regular SIGUSR1 path only runs on POSIX systems")

        with (
            patch("app.library.downloads.process_manager.os.kill") as mock_kill,
            patch(
                "app.library.downloads.process_manager.wait_for_process_with_timeout", return_value=True
            ) as mock_wait,
        ):
            assert pm_regular.kill() is True, "Regular downloads should keep SIGUSR1 behavior"
            mock_kill.assert_called_once_with(12346, signal.SIGUSR1)
            mock_wait.assert_called_once_with(pm_regular.proc, 5)

    @pytest.mark.asyncio
    async def test_close_returns_false_when_not_started(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)

        result = await pm.close()
        assert result is False, "Should return False when process not started"

    @pytest.mark.asyncio
    async def test_close_returns_false_when_cancel_in_progress(self) -> None:
        logger = logging.getLogger("test")
        pm = ProcessManager("test-id", is_live=False, logger=logger)
        pm.proc = Mock()
        pm.cancel_in_progress = True

        result = await pm.close()
        assert result is False, "Should return False when cancellation already in progress"

    @pytest.mark.asyncio
    async def test_close_kills_and_joins_process(self) -> None:
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

    def test_init_sets_attributes(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        assert st.id == "test-id", "Should set download ID"
        assert st.info == mock_config["info"], "Should set info reference"
        assert st.tmpfilename is None, "Should initialize tmpfilename as None"
        assert st.final_update is False, "Should initialize final_update as False"

    @pytest.mark.asyncio
    async def test_process_status_update_ignores_invalid_id(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "wrong-id", "status": "downloading"}

        await st.process_status_update(status)
        assert st.info.status != "downloading", "Should not update status for wrong ID"

    @pytest.mark.asyncio
    async def test_process_status_update_ignores_short_status(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id"}

        await st.process_status_update(status)

    @pytest.mark.asyncio
    async def test_process_status_update_sets_status(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "downloaded_bytes": 1000}

        await st.process_status_update(status)
        assert st.info.status == "downloading", "Should update info status"

    @pytest.mark.asyncio
    async def test_process_status_update_sets_download_skipped(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "download_skipped": True}

        await st.process_status_update(status)
        assert st.info.download_skipped is True, "Should update download_skipped from status queue"

    @pytest.mark.asyncio
    async def test_process_status_update_sets_tmpfilename(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "tmpfilename": "/tmp/file.part"}

        await st.process_status_update(status)
        assert st.tmpfilename == "/tmp/file.part", "Should update tmpfilename"

    @pytest.mark.asyncio
    async def test_process_status_update_calculates_percent(self, mock_config: dict) -> None:
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
    async def test_process_status_update_uses_estimated_total(self, mock_config: dict) -> None:
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
    async def test_process_status_update_handles_zero_division(self, mock_config: dict) -> None:
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
    async def test_process_status_update_sets_speed_and_eta(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "downloading", "speed": 1024000, "eta": 60}

        await st.process_status_update(status)
        assert st.info.speed == 1024000, "Should set speed"
        assert st.info.eta == 60, "Should set eta"

    @pytest.mark.asyncio
    async def test_process_status_update_sets_error(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        status = {"id": "test-id", "status": "error", "error": "Download failed"}

        await st.process_status_update(status)
        assert st.info.status == "error", "Should set status to error"
        assert st.info.error == "Download failed", "Should set error message"

    @pytest.mark.asyncio
    async def test_process_status_update_sets_final_update(self, tmp_path: Path, mock_config: dict) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")

        st = StatusTracker(**mock_config)
        st.download_dir = str(tmp_path)
        status = {"id": "test-id", "status": "finished", "final_name": str(test_file)}

        await st.process_status_update(status)
        assert st.final_update is True, "Should set final_update when final file exists"
        assert st.info.filename == "test.mp4", "Should set relative filename"

    @pytest.mark.asyncio
    async def test_drain_queue_processes_remaining_updates(self, mock_config: dict) -> None:
        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 100})
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 200})
        queue.put(Terminator())

        config = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=10)
        assert st.info.downloaded_bytes == 200, "Should process all queued updates"

    @pytest.mark.asyncio
    async def test_drain_queue_stops_on_final_update(self, tmp_path: Path, mock_config: dict) -> None:
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")

        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "finished", "final_name": str(test_file)})
        queue.put({"id": "test-id", "status": "downloading", "downloaded_bytes": 999})

        config = {**mock_config, "status_queue": queue, "download_dir": str(tmp_path)}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=10)
        assert st.final_update is True, "Should stop draining after final update"

    @pytest.mark.asyncio
    async def test_drain_queue_handles_errors_gracefully(self, mock_config: dict) -> None:
        queue = DummyQueue()
        queue.put({"id": "test-id", "status": "downloading"})
        queue.put(None)

        config = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        await st.drain_queue(max_iterations=5)

    def test_cancel_update_task_cancels_running_task(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)
        st.update_task = Mock()
        st.update_task.done = Mock(return_value=False)
        st.update_task.cancel = Mock()

        st.cancel_update_task()
        st.update_task.cancel.assert_called_once()

    def test_cancel_update_task_handles_no_task(self, mock_config: dict) -> None:
        st = StatusTracker(**mock_config)

        st.cancel_update_task()

    def test_put_terminator_adds_to_queue(self, mock_config: dict) -> None:
        queue = DummyQueue()
        config = {**mock_config, "status_queue": queue}
        st = StatusTracker(**config)

        st.put_terminator()
        assert 1 == len(queue.items), "Should add terminator to queue"
        assert isinstance(queue.items[0], Terminator), "Should add Terminator instance"


class TestQueueManager:
    @pytest.mark.asyncio
    async def test_cancel_running_live_item_defers_close(self) -> None:
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
    async def test_cancel_running_regular_item_closes_immediately(self) -> None:
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


class TestPoolManager:
    @pytest.mark.asyncio
    async def test_cancelled_entry_with_final_file_stays_finished(self, monkeypatch: pytest.MonkeyPatch) -> None:
        emitted_events: list[str] = []

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(event, **_kwargs):
                emitted_events.append(event)

        monkeypatch.setattr("app.library.downloads.pool_manager.EventBus", EB)

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
    async def test_cancelled_regular_entry_with_final_file_stays_cancelled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        emitted_events: list[str] = []

        class EB:
            @staticmethod
            def get_instance():
                return EB

            @staticmethod
            def emit(event, **_kwargs):
                emitted_events.append(event)

        monkeypatch.setattr("app.library.downloads.pool_manager.EventBus", EB)

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
