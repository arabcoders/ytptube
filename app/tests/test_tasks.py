import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.library.Tasks import Task, Tasks


class TestTask:
    """Test the Task dataclass."""

    def test_task_creation_with_required_fields(self):
        """Test creating a task with only required fields."""
        task = Task(id="test_id", name="test_task", url="https://example.com/video")

        assert task.id == "test_id"
        assert task.name == "test_task"
        assert task.url == "https://example.com/video"
        assert task.folder == ""
        assert task.preset == ""
        assert task.timer == ""
        assert task.template == ""
        assert task.cli == ""
        assert task.auto_start is True
        assert task.handler_enabled is True
        assert task.enabled is True

    def test_task_creation_with_all_fields(self):
        """Test creating a task with all fields specified."""
        task = Task(
            id="test_id",
            name="test_task",
            url="https://example.com/video",
            folder="test_folder",
            preset="test_preset",
            timer="0 */6 * * *",
            template="%(title)s.%(ext)s",
            cli="--extract-flat",
            auto_start=False,
            handler_enabled=False,
            enabled=False,
        )

        assert task.id == "test_id"
        assert task.name == "test_task"
        assert task.url == "https://example.com/video"
        assert task.folder == "test_folder"
        assert task.preset == "test_preset"
        assert task.timer == "0 */6 * * *"
        assert task.template == "%(title)s.%(ext)s"
        assert task.cli == "--extract-flat"
        assert task.auto_start is False
        assert task.handler_enabled is False
        assert task.enabled is False

    def test_task_serialize(self):
        """Test task serialization to dictionary."""
        task = Task(
            id="test_id",
            name="test_task",
            url="https://example.com/video",
            preset="test_preset",
        )

        serialized = task.serialize()

        assert isinstance(serialized, dict)
        assert serialized["id"] == "test_id"
        assert serialized["name"] == "test_task"
        assert serialized["url"] == "https://example.com/video"
        assert serialized["preset"] == "test_preset"
        assert serialized["folder"] == ""
        assert serialized["auto_start"] is True

    @patch("app.library.Tasks.Encoder")
    def test_task_json(self, mock_encoder):
        """Test task JSON serialization."""
        mock_encoder_instance = Mock()
        mock_encoder_instance.encode.return_value = '{"id": "test_id"}'
        mock_encoder.return_value = mock_encoder_instance

        task = Task(id="test_id", name="test_task", url="https://example.com/video")

        json_str = task.json()

        assert json_str == '{"id": "test_id"}'
        mock_encoder_instance.encode.assert_called_once()

    def test_task_get_method(self):
        """Test task get method for accessing fields."""
        task = Task(
            id="test_id",
            name="test_task",
            url="https://example.com/video",
            preset="test_preset",
        )

        assert task.get("id") == "test_id"
        assert task.get("name") == "test_task"
        assert task.get("preset") == "test_preset"
        assert task.get("nonexistent") is None
        assert task.get("nonexistent", "default_value") == "default_value"

    @patch("app.library.Tasks.YTDLPOpts")
    def test_task_get_ytdlp_opts_without_preset_or_cli(self, mock_ytdlp_opts):
        """Test getting YTDLPOpts without preset or CLI options."""
        mock_opts_instance = Mock()
        mock_ytdlp_opts.get_instance.return_value = mock_opts_instance

        task = Task(id="test_id", name="test_task", url="https://example.com/video")

        result = task.get_ytdlp_opts()

        assert result == mock_opts_instance
        mock_ytdlp_opts.get_instance.assert_called_once()

    @patch("app.library.Tasks.YTDLPOpts")
    def test_task_get_ytdlp_opts_with_preset_and_cli(self, mock_ytdlp_opts):
        """Test getting YTDLPOpts with preset and CLI options."""
        mock_opts_instance = Mock()
        mock_preset_opts = Mock()
        mock_final_opts = Mock()

        mock_opts_instance.preset.return_value = mock_preset_opts
        mock_preset_opts.add_cli.return_value = mock_final_opts
        mock_ytdlp_opts.get_instance.return_value = mock_opts_instance

        task = Task(
            id="test_id",
            name="test_task",
            url="https://example.com/video",
            preset="test_preset",
            cli="--extract-flat",
        )

        result = task.get_ytdlp_opts()

        assert result == mock_final_opts
        mock_opts_instance.preset.assert_called_once_with(name="test_preset")
        mock_preset_opts.add_cli.assert_called_once_with("--extract-flat", from_user=True)

    @patch("app.library.Tasks.archive_add")
    @patch("app.library.Tasks.extract_info")
    def test_task_mark_success(self, mock_extract_info, mock_archive_add):
        """Test successful task marking."""
        # Mock extract_info to return playlist data
        mock_extract_info.return_value = {
            "_type": "playlist",
            "entries": [
                {
                    "_type": "video",
                    "id": "video1",
                    "ie_key": "Youtube",
                },
                {
                    "_type": "video",
                    "id": "video2",
                    "ie_key": "Youtube",
                },
            ],
        }
        mock_archive_add.return_value = True

        with patch.object(Task, "get_ytdlp_opts") as mock_get_opts:
            mock_get_opts.return_value.get_all.return_value = {"download_archive": "/tmp/archive.txt"}

            task = Task(id="test_id", name="test_task", url="https://example.com/playlist")

            success, message = task.mark()

            assert success is True
            assert "marked as downloaded" in message
            mock_archive_add.assert_called_once()
            # Check that archive_add was called with the correct items
            call_args = mock_archive_add.call_args[0]
            archive_file = call_args[0]
            items = call_args[1]
            assert str(archive_file) == "/tmp/archive.txt"
            assert "youtube video1" in items
            assert "youtube video2" in items

    def test_task_mark_no_url(self):
        """Test task marking with no URL."""
        task = Task(id="test_id", name="test_task", url="")

        success, message = task.mark()

        assert success is False
        assert "No URL found" in message

    def test_task_mark_no_archive_file(self):
        """Test task marking with no archive file configured."""
        with patch.object(Task, "get_ytdlp_opts") as mock_get_opts:
            mock_get_opts.return_value.get_all.return_value = {}

            task = Task(id="test_id", name="test_task", url="https://example.com/video")

            success, message = task.mark()

            assert success is False
            assert "No archive file found" in message

    @patch("app.library.Tasks.archive_delete")
    @patch("app.library.Tasks.extract_info")
    def test_task_unmark_success(self, mock_extract_info, mock_archive_delete):
        """Test successful task unmarking."""
        # Mock extract_info to return playlist data
        mock_extract_info.return_value = {
            "_type": "playlist",
            "entries": [
                {
                    "_type": "video",
                    "id": "video1",
                    "ie_key": "Youtube",
                },
            ],
        }
        mock_archive_delete.return_value = True

        with patch.object(Task, "get_ytdlp_opts") as mock_get_opts:
            mock_get_opts.return_value.get_all.return_value = {"download_archive": "/tmp/archive.txt"}

            task = Task(id="test_id", name="test_task", url="https://example.com/playlist")

            success, message = task.unmark()

            assert success is True
            assert "Removed" in message
            assert "items from archive file" in message
            mock_archive_delete.assert_called_once()

    @patch("app.library.Tasks.extract_info")
    def test_task_mark_logic_invalid_extract_info(self, mock_extract_info):
        """Test _mark_logic with invalid extract_info response."""
        mock_extract_info.return_value = None

        with patch.object(Task, "get_ytdlp_opts") as mock_get_opts:
            mock_get_opts.return_value.get_all.return_value = {"download_archive": "/tmp/archive.txt"}

            task = Task(id="test_id", name="test_task", url="https://example.com/video")

            result = task._mark_logic()

            assert isinstance(result, tuple)
            success, message = result
            assert success is False
            assert "Failed to extract information" in message

    @patch("app.library.Tasks.extract_info")
    def test_task_mark_logic_not_playlist(self, mock_extract_info):
        """Test _mark_logic with non-playlist type."""
        mock_extract_info.return_value = {
            "_type": "video",
            "id": "video1",
        }

        with patch.object(Task, "get_ytdlp_opts") as mock_get_opts:
            mock_get_opts.return_value.get_all.return_value = {"download_archive": "/tmp/archive.txt"}

            task = Task(id="test_id", name="test_task", url="https://example.com/video")

            result = task._mark_logic()

            assert isinstance(result, tuple)
            success, message = result
            assert success is False
            assert "Expected a playlist type" in message


class TestTasks:
    """Test the Tasks singleton manager."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Reset singleton instance to ensure clean state
        Tasks._reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        # Reset singleton instance to prevent test pollution
        Tasks._reset_singleton()

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_singleton(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test that Tasks follows singleton pattern."""
        mock_config.get_instance.return_value = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        instance1 = Tasks.get_instance()
        instance2 = Tasks.get_instance()

        assert instance1 is instance2
        assert isinstance(instance1, Tasks)

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_initialization(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test Tasks initialization with proper dependencies."""
        mock_config_instance = Mock(
            debug=True, default_preset="test_preset", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance
        mock_scheduler_instance = Mock()
        mock_scheduler.get_instance.return_value = mock_scheduler_instance
        mock_download_queue_instance = Mock()
        mock_download_queue.get_instance.return_value = mock_download_queue_instance

        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_file = Path(temp_dir) / "tasks.json"
            tasks = Tasks(file=tasks_file, config=mock_config_instance)

            # Check initialization
            assert tasks._debug is True
            assert tasks._default_preset == "test_preset"
            assert tasks._file == tasks_file
            assert tasks._tasks == []
            assert tasks._scheduler == mock_scheduler_instance
            assert tasks._notify == mock_eventbus_instance
            assert tasks._downloadQueue == mock_download_queue_instance

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_get_all_empty(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test getting all tasks when no tasks exist."""
        mock_config.get_instance.return_value = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks.get_instance()

        result = tasks.get_all()

        assert result == []
        assert isinstance(result, list)

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_get_by_id_not_found(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test getting task by ID when task doesn't exist."""
        mock_config.get_instance.return_value = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks.get_instance()

        result = tasks.get("nonexistent_id")

        assert result is None

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_load_empty_file(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test loading tasks from empty or non-existent file."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_file = Path(temp_dir) / "nonexistent.json"
            tasks = Tasks(file=tasks_file, config=mock_config_instance)

            result = tasks.load()

            assert result == tasks  # Should return self
            assert tasks.get_all() == []

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_load_valid_file(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test loading tasks from valid JSON file."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler_instance = Mock()
        mock_scheduler.get_instance.return_value = mock_scheduler_instance
        mock_download_queue.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_file = Path(temp_dir) / "tasks.json"

            # Create valid JSON file with task data
            task_data = [
                {
                    "id": "task1",
                    "name": "Test Task 1",
                    "url": "https://example.com/video1",
                    "preset": "default",
                    "timer": "0 6 * * *",
                    "folder": "",
                    "template": "",
                    "cli": "",
                    "auto_start": True,
                    "handler_enabled": True,
                }
            ]
            tasks_file.write_text("[\n" + "\n".join(f"    {line}" for line in str(task_data).split("\n")) + "\n]")

            # Mock json.loads to return our test data
            with patch("json.loads", return_value=task_data):
                tasks = Tasks(file=tasks_file, config=mock_config_instance)

                # Mock the scheduler.add method
                mock_scheduler_instance.add = Mock()

                result = tasks.load()

                assert result == tasks
                loaded_tasks = tasks.get_all()
                assert len(loaded_tasks) == 1
                assert loaded_tasks[0].id == "task1"
                assert loaded_tasks[0].name == "Test Task 1"
                assert loaded_tasks[0].url == "https://example.com/video1"

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_load_invalid_json(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test loading tasks from file with invalid JSON."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_file = Path(temp_dir) / "tasks.json"
            tasks_file.write_text("invalid json {")

            tasks = Tasks(file=tasks_file, config=mock_config_instance)

            result = tasks.load()

            assert result == tasks
            assert tasks.get_all() == []  # Should be empty due to invalid JSON

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_save_valid_tasks(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test saving valid tasks to file."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            tasks_file = Path(temp_dir) / "tasks.json"
            tasks = Tasks(file=tasks_file, config=mock_config_instance)

            task_data = [
                {
                    "id": "task1",
                    "name": "Test Task",
                    "url": "https://example.com/video",
                    "preset": "default",
                    "folder": "",
                    "template": "",
                    "cli": "",
                    "timer": "",
                    "auto_start": True,
                    "handler_enabled": True,
                }
            ]

            result = tasks.save(task_data)

            assert result == tasks
            assert tasks_file.exists()
            # Verify file content was written
            assert tasks_file.stat().st_size > 0

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_get_by_id_found(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test getting task by ID when task exists."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks(file=None, config=mock_config_instance)

        # Manually add a task to the internal list
        test_task = Task(id="test_id", name="Test Task", url="https://example.com/video")
        tasks._tasks.append(test_task)

        result = tasks.get("test_id")

        assert result is not None
        assert result.id == "test_id"
        assert result.name == "Test Task"

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_get_all_with_tasks(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test getting all tasks when tasks exist."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks(file=None, config=mock_config_instance)

        # Manually add tasks to the internal list
        task1 = Task(id="task1", name="Task 1", url="https://example.com/video1")
        task2 = Task(id="task2", name="Task 2", url="https://example.com/video2")
        tasks._tasks.extend([task1, task2])

        result = tasks.get_all()

        assert len(result) == 2
        assert result[0].id == "task1"
        assert result[1].id == "task2"

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_clear_with_scheduler_cleanup(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test clearing tasks with scheduler cleanup."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler_instance = Mock()
        mock_scheduler_instance.has.return_value = True
        mock_scheduler_instance.remove = Mock()
        mock_scheduler.get_instance.return_value = mock_scheduler_instance
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks(file=None, config=mock_config_instance)

        # Add a task with timer to the internal list
        task_with_timer = Task(id="task1", name="Task 1", url="https://example.com/video1", timer="0 6 * * *")
        tasks._tasks.append(task_with_timer)

        result = tasks.clear()

        assert result == tasks
        assert len(tasks.get_all()) == 0
        mock_scheduler_instance.has.assert_called_with("task1")
        mock_scheduler_instance.remove.assert_called_with("task1")

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_clear_no_tasks(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test clearing when no tasks exist."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler_instance = Mock()
        mock_scheduler.get_instance.return_value = mock_scheduler_instance
        mock_download_queue.get_instance.return_value = Mock()

        tasks = Tasks(file=None, config=mock_config_instance)

        result = tasks.clear()

        assert result == tasks
        assert len(tasks.get_all()) == 0
        # Should not call scheduler methods when no tasks exist
        mock_scheduler_instance.has.assert_not_called()
        mock_scheduler_instance.remove.assert_not_called()

    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    def test_tasks_validate_valid_task_dict(self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config):
        """Test task validation with valid task dictionary."""
        mock_config.get_instance.return_value = Mock()
        mock_eventbus.get_instance.return_value = Mock()
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue.get_instance.return_value = Mock()

        valid_task = {
            "name": "Test Task",
            "url": "https://example.com/video",
            "timer": "0 6 * * *",
            "cli": "--write-info-json",
        }

        with patch("app.library.Tasks.validate_url") as mock_validate_url:
            mock_validate_url.return_value = True

            result = Tasks.validate(valid_task)

            assert result is True
            mock_validate_url.assert_called_once_with("https://example.com/video", allow_internal=True)

    def test_tasks_validate_invalid_task_type(self):
        """Test task validation with invalid task type."""
        invalid_task = "not a dict or Task"

        with pytest.raises(ValueError, match="Invalid task type"):
            Tasks.validate(invalid_task)

    def test_tasks_validate_missing_name(self):
        """Test task validation with missing name."""
        invalid_task = {
            "url": "https://example.com/video",
        }

        with pytest.raises(ValueError, match="No name found"):
            Tasks.validate(invalid_task)

    def test_tasks_validate_missing_url(self):
        """Test task validation with missing URL."""
        invalid_task = {
            "name": "Test Task",
        }

        with pytest.raises(ValueError, match="No URL found"):
            Tasks.validate(invalid_task)

    def test_tasks_validate_invalid_url(self):
        """Test task validation with invalid URL."""
        invalid_task = {
            "name": "Test Task",
            "url": "invalid-url",
        }

        with patch("app.library.Tasks.validate_url") as mock_validate_url:
            mock_validate_url.side_effect = ValueError("Invalid URL")

            with pytest.raises(ValueError, match="Invalid URL format"):
                Tasks.validate(invalid_task)

    def test_tasks_validate_invalid_timer(self):
        """Test task validation with invalid timer format."""
        invalid_task = {
            "name": "Test Task",
            "url": "https://example.com/video",
            "timer": "invalid timer",
        }

        with patch("app.library.Tasks.validate_url") as mock_validate_url:
            mock_validate_url.return_value = True

            # Import error will be raised by cronsim for invalid format
            with patch("cronsim.CronSim") as mock_cronsim:
                mock_cronsim.side_effect = Exception("Invalid cron format")

                with pytest.raises(ValueError, match="Invalid timer format"):
                    Tasks.validate(invalid_task)

    def test_tasks_validate_invalid_cli(self):
        """Test task validation with invalid CLI options."""
        invalid_task = {
            "name": "Test Task",
            "url": "https://example.com/video",
            "cli": "invalid --cli options",
        }

        with patch("app.library.Tasks.validate_url") as mock_validate_url:
            mock_validate_url.return_value = True

            with patch("app.library.Utils.arg_converter") as mock_arg_converter:
                mock_arg_converter.side_effect = Exception("Invalid CLI args")

                with pytest.raises(ValueError, match="Invalid command options for yt-dlp"):
                    Tasks.validate(invalid_task)

    @pytest.mark.asyncio
    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    @patch("app.library.Tasks.Item")
    @patch("app.library.Tasks.datetime")
    @patch("app.library.Tasks.time")
    async def test_tasks_runner_success(
        self, mock_time, mock_datetime, mock_item, mock_download_queue, mock_scheduler, mock_eventbus, mock_config
    ):
        """Test successful task runner execution."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance
        mock_scheduler.get_instance.return_value = Mock()

        # Mock download queue
        mock_download_queue_instance = Mock()
        mock_download_queue_instance.add = AsyncMock(return_value={"success": True, "id": "download123"})
        mock_download_queue.get_instance.return_value = mock_download_queue_instance

        # Mock time and datetime
        mock_time.time.side_effect = [1000.0, 1005.5]  # start and end times
        mock_datetime_instance = Mock()
        mock_datetime_instance.isoformat.return_value = "2024-01-01T12:00:00Z"
        mock_datetime.now.return_value = mock_datetime_instance

        # Mock Item.format
        mock_item.format.return_value = {"formatted": "item"}

        tasks = Tasks(file=None, config=mock_config_instance)

        test_task = Task(
            id="task1",
            name="Test Task",
            url="https://example.com/video",
            preset="test_preset",
            folder="test_folder",
            template="test_template",
            cli="--write-info-json",
            auto_start=True,
            enabled=True,
        )

        # Add task to tasks list so it can be found by _runner
        tasks._tasks.append(test_task)

        await tasks._runner(test_task)

        # Verify download queue was called
        mock_download_queue_instance.add.assert_called_once()

        # Verify Item.format was called with correct parameters
        mock_item.format.assert_called_once_with(
            {
                "url": "https://example.com/video",
                "preset": "test_preset",
                "folder": "test_folder",
                "template": "test_template",
                "cli": "--write-info-json",
                "auto_start": True,
                "extras": {
                    "source_name": "Test Task",
                    "source_id": "task1",
                    "source_handler": "Tasks",
                },
            }
        )

        # Verify events were emitted
        assert mock_eventbus_instance.emit.call_count == 2

    @pytest.mark.asyncio
    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    @patch("app.library.Tasks.datetime")
    async def test_tasks_runner_no_url(
        self, mock_datetime, mock_download_queue, mock_scheduler, mock_eventbus, mock_config
    ):
        """Test task runner with no URL."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance
        mock_scheduler.get_instance.return_value = Mock()
        mock_download_queue_instance = Mock()
        mock_download_queue.get_instance.return_value = mock_download_queue_instance

        mock_datetime_instance = Mock()
        mock_datetime_instance.isoformat.return_value = "2024-01-01T12:00:00Z"
        mock_datetime.now.return_value = mock_datetime_instance

        tasks = Tasks(file=None, config=mock_config_instance)

        test_task = Task(
            id="task1",
            name="Test Task",
            url="",  # Empty URL to trigger error
            enabled=True,
        )

        # Add task to tasks list so it can be found by _runner
        tasks._tasks.append(test_task)

        await tasks._runner(test_task)

        # Verify download queue was NOT called
        mock_download_queue_instance.add.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    @patch("app.library.Tasks.Item")
    @patch("app.library.Tasks.datetime")
    async def test_tasks_runner_download_queue_failure(
        self, mock_datetime, mock_item, mock_download_queue, mock_scheduler, mock_eventbus, mock_config
    ):
        """Test task runner when download queue add fails."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance
        mock_scheduler.get_instance.return_value = Mock()

        # Mock download queue to raise exception
        mock_download_queue_instance = Mock()
        mock_download_queue_instance.add = AsyncMock(side_effect=Exception("Queue error"))
        mock_download_queue.get_instance.return_value = mock_download_queue_instance

        mock_datetime_instance = Mock()
        mock_datetime_instance.isoformat.return_value = "2024-01-01T12:00:00Z"
        mock_datetime.now.return_value = mock_datetime_instance

        mock_item.format.return_value = {"formatted": "item"}

        tasks = Tasks(file=None, config=mock_config_instance)

        test_task = Task(
            id="task1",
            name="Test Task",
            url="https://example.com/video",
            enabled=True,
        )

        # Add task to tasks list so it can be found by _runner
        tasks._tasks.append(test_task)

        await tasks._runner(test_task)

        # Verify error event was emitted (check last call)
        calls = mock_eventbus_instance.emit.call_args_list
        assert len(calls) > 0
        # Verify the last call was an error event
        last_call = calls[-1]
        assert "Task failed" in str(last_call)

    @pytest.mark.asyncio
    @patch("app.library.Tasks.Config")
    @patch("app.library.Tasks.EventBus")
    @patch("app.library.Tasks.Scheduler")
    @patch("app.library.Tasks.DownloadQueue")
    async def test_tasks_runner_disabled_task(
        self, mock_download_queue, mock_scheduler, mock_eventbus, mock_config
    ):
        """Test that disabled tasks are skipped by the runner."""
        mock_config_instance = Mock(
            debug=False, default_preset="default", config_path="/tmp", tasks_handler_timer="15 */1 * * *"
        )
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance
        mock_scheduler.get_instance.return_value = Mock()

        # Mock download queue
        mock_download_queue_instance = Mock()
        mock_download_queue_instance.add = AsyncMock(return_value={"success": True, "id": "download123"})
        mock_download_queue.get_instance.return_value = mock_download_queue_instance

        tasks = Tasks(file=None, config=mock_config_instance)

        test_task = Task(
            id="task1",
            name="Test Task",
            url="https://example.com/video",
            enabled=False,  # Task is disabled
        )

        # Add task to tasks list so it can be found by _runner
        tasks._tasks.append(test_task)

        await tasks._runner(test_task)

        # Verify download queue was NOT called (task was skipped)
        mock_download_queue_instance.add.assert_not_called()
