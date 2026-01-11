import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestFFProbe:
    """Test the ffprobe module functionality."""

    def setup_method(self):
        """Set up test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_video.mp4"
        self.test_file.touch()

    def teardown_method(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_ffprobe_with_existing_file(self):
        """Test ffprobe with an existing file."""
        from app.library.ffprobe import FFProbeResult, ffprobe

        # Mock subprocess to avoid actual ffprobe execution
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock the subprocess result
            mock_process = AsyncMock()
            mock_process.wait.return_value = 0
            mock_process.communicate.return_value = (b'{"format": {"duration": "10.0"}}', b"")
            mock_subprocess.return_value = mock_process

            with patch("anyio.open_file") as mock_open_file:
                mock_file = AsyncMock()
                mock_open_file.return_value.__aenter__.return_value = mock_file

                result = await ffprobe(str(self.test_file))
                assert isinstance(result, FFProbeResult)

    @pytest.mark.asyncio
    async def test_ffprobe_with_nonexistent_file(self):
        """Test ffprobe with a non-existent file."""
        from app.library.ffprobe import ffprobe

        nonexistent_file = Path(self.temp_dir) / "does_not_exist.mp4"

        with pytest.raises(OSError, match="No such media file"):
            await ffprobe(str(nonexistent_file))

    @pytest.mark.asyncio
    async def test_ffprobe_caching_behavior(self):
        """Test that ffprobe results are cached with enhanced async timed_lru_cache."""
        from app.library.ffprobe import ffprobe

        assert hasattr(ffprobe, "cache_clear"), (
            "Test that the function has been decorated with caching - ffprobe should have cache_clear method from timed_lru_cache"
        )
        assert hasattr(ffprobe, "cache_info"), "ffprobe should have cache_info method from timed_lru_cache"

        # Clear cache to start fresh
        ffprobe.cache_clear()

        # Mock subprocess to avoid actual ffprobe execution
        call_count = 0
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:

            def create_mock_process(*_args, **_kwargs):
                nonlocal call_count
                call_count += 1
                mock_process = AsyncMock()
                mock_process.wait.return_value = 0
                mock_process.communicate.return_value = (b'{"format": {"duration": "10.0"}, "streams": []}', b"")
                return mock_process

            mock_subprocess.side_effect = create_mock_process

            with patch("anyio.open_file") as mock_open_file:
                mock_file = AsyncMock()
                mock_open_file.return_value.__aenter__.return_value = mock_file

                # First call should execute the function
                result1 = await ffprobe(str(self.test_file))
                assert result1 is not None
                assert isinstance(result1.metadata, dict)
                first_call_count = call_count

                # Second call with same argument should use cached result
                result2 = await ffprobe(str(self.test_file))
                assert result2 is not None
                assert isinstance(result2.metadata, dict)

                assert call_count == first_call_count, (
                    "The subprocess should not be called again for the actual ffprobe execution (it may be called for the -h check, but the main execution should be cached) - Second call should use cached result"
                )

                assert result1.metadata == result2.metadata, (
                    "Results should be equivalent (same data, may not be same object due to async nature)"
                )

    @pytest.mark.asyncio
    async def test_ffprobe_with_path_object(self):
        """Test ffprobe with Path object input."""
        from app.library.ffprobe import ffprobe

        # Mock subprocess to avoid actual ffprobe execution
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.wait.return_value = 0
            mock_process.communicate.return_value = (b'{"format": {"duration": "10.0"}}', b"")
            mock_subprocess.return_value = mock_process

            with patch("anyio.open_file") as mock_open_file:
                mock_file = AsyncMock()
                mock_open_file.return_value.__aenter__.return_value = mock_file

                # Test with Path object
                result = await ffprobe(self.test_file)
                assert result is not None

    def test_ffprobe_result_properties(self):
        """Test FFProbeResult object properties."""
        from app.library.ffprobe import FFProbeResult, FFStream

        result = FFProbeResult()

        assert result.video == [], "Test empty result"
        assert result.audio == []
        assert result.subtitle == []
        assert result.attachment == []
        assert result.metadata == {}

        # Test adding streams
        video_stream = FFStream(
            {"index": 0, "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}
        )

        audio_stream = FFStream({"index": 1, "codec_type": "audio", "codec_name": "aac", "channels": 2})

        result.video.append(video_stream)
        result.audio.append(audio_stream)

        assert len(result.video) == 1
        assert len(result.audio) == 1
        assert result.video[0].is_video()
        assert result.audio[0].is_audio()

    def test_stream_object_methods(self):
        """Test Stream object methods."""
        from app.library.ffprobe import FFStream

        # Test video stream
        video_stream = FFStream(
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "duration": "10.5"}
        )

        assert video_stream.is_video()
        assert not video_stream.is_audio()
        assert not video_stream.is_subtitle()
        assert not video_stream.is_attachment()

        # Test audio stream
        audio_stream = FFStream({"codec_type": "audio", "codec_name": "aac", "channels": 2, "sample_rate": "44100"})

        assert not audio_stream.is_video()
        assert audio_stream.is_audio()
        assert not audio_stream.is_subtitle()
        assert not audio_stream.is_attachment()

        # Test subtitle stream
        subtitle_stream = FFStream({"codec_type": "subtitle", "codec_name": "subrip"})

        assert not subtitle_stream.is_video()
        assert not subtitle_stream.is_audio()
        assert subtitle_stream.is_subtitle()
        assert not subtitle_stream.is_attachment()

        # Test attachment stream
        attachment_stream = FFStream({"codec_type": "attachment", "codec_name": "ttf"})

        assert not attachment_stream.is_video()
        assert not attachment_stream.is_audio()
        assert not attachment_stream.is_subtitle()
        assert attachment_stream.is_attachment()
