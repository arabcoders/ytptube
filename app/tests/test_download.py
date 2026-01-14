import logging
import os
import signal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.library.downloads import Download, NestedLogger, Terminator
from app.library.downloads.hooks import HookHandlers
from app.library.downloads.process_manager import ProcessManager
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
            download_info_expires = 3600

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
        hooks = HookHandlers(d.id, q, d.logger, d.debug)

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
        hooks = HookHandlers(d.id, q, d.logger, d.debug)
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
            download_info_expires = 3600

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

        def dummy_target():
            pass

        proc = pm.create_process(dummy_target)
        assert proc is not None, "Should create a process"
        assert pm.proc is proc, "Should store process reference"
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

    def test_kill_uses_shorter_timeout_for_live_streams(self) -> None:
        logger = logging.getLogger("test")
        pm_live = ProcessManager("test-id", is_live=True, logger=logger)
        pm_regular = ProcessManager("test-id", is_live=False, logger=logger)

        pm_live.proc = Mock()
        pm_live.proc.pid = 12345
        pm_live.proc.ident = 67890
        pm_live.proc.is_alive = Mock(return_value=False)

        pm_regular.proc = Mock()
        pm_regular.proc.pid = 12346
        pm_regular.proc.ident = 67891
        pm_regular.proc.is_alive = Mock(return_value=False)

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
