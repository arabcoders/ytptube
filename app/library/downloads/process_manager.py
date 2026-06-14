"""Process lifecycle management for downloads."""

import logging
import multiprocessing
import os
import signal
from collections.abc import Callable

from app.library.config import Config

from .utils import wait_for_process_with_timeout


class ProcessManager:
    """
    Manages the lifecycle of a download subprocess.

    Handles process creation, monitoring, graceful termination, and
    force-kill operations. Includes special handling for live streams
    which may not respond to standard termination signals.
    """

    def __init__(self, download_id: str, is_live: bool, logger: logging.Logger):
        """
        Initialize process manager.

        Args:
            download_id: Unique identifier for this download
            is_live: Whether this is a live stream download
            logger: Logger instance

        """
        self.download_id = download_id
        self.is_live = is_live
        self.logger = logger
        self._context = multiprocessing.get_context()
        self.proc: multiprocessing.Process | None = None
        self.cancel_event = Config.get_manager().Event()
        self.cancelled = False
        self.cancel_in_progress = False

    def create_process(self, target: Callable[[], None]) -> multiprocessing.Process:
        """
        Create a new download process.

        Args:
            target: Function to execute in the subprocess

        Returns:
            Created but not started process

        """
        self.cancel_event.clear()
        self.proc = self._context.Process(name=f"download-{self.download_id}", target=target)
        return self.proc

    def start(self) -> None:
        if self.proc:
            self.proc.start()

    def started(self) -> bool:
        return self.proc is not None

    def running(self) -> bool:
        try:
            return self.proc is not None and self.proc.is_alive()
        except ValueError:
            return False

    def is_cancelled(self) -> bool:
        return self.cancelled

    def cancel(self) -> bool:
        """
        Mark download as cancelled and kill the process.

        Returns:
            True if cancellation was initiated, False otherwise

        """
        if not self.started():
            return False

        self.cancelled = True
        return self.kill()

    def kill(self) -> bool:
        """
        Kill the download process.

        Attempts graceful termination first, then escalates to terminate() and
        finally kill() if needed. Live streams use a shared cancel event so the
        worker can raise SIGINT inside itself and let yt-dlp finalize cleanly.

        Returns:
            True if process was killed successfully, False otherwise

        """
        if not self.running():
            return False

        proc = self.proc
        if proc is None:
            return False

        procId: int | None = proc.ident
        try:
            self.logger.info(
                "Stopping download process PID=%s.",
                proc.pid,
                extra={
                    "download": {
                        "download_id": self.download_id,
                        "process_id": proc.pid,
                        "process_ident": procId,
                        "is_live": self.is_live,
                    }
                },
            )

            if self.is_live:
                self.logger.debug(
                    "Requesting graceful live cancellation for PID=%s.",
                    proc.pid,
                    extra={
                        "download": {
                            "download_id": self.download_id,
                            "process_id": proc.pid,
                            "is_live": self.is_live,
                        }
                    },
                )
                self.cancel_event.set()

                if wait_for_process_with_timeout(proc, 10):
                    self.logger.debug(
                        "Download process PID=%s stopped gracefully.",
                        proc.pid,
                        extra={
                            "download": {
                                "download_id": self.download_id,
                                "process_id": proc.pid,
                                "is_live": self.is_live,
                            }
                        },
                    )
                    return True
                self.logger.warning(
                    "Download process PID=%s did not respond to live cancellation; forcing termination.",
                    proc.pid,
                    extra={
                        "download": {
                            "download_id": self.download_id,
                            "process_id": proc.pid,
                            "is_live": self.is_live,
                            "force": True,
                        }
                    },
                )

            elif proc.pid and "posix" == os.name:
                signal_name = "SIGUSR1"

                try:
                    self.logger.debug(
                        "Sending %s signal to download process PID=%s.",
                        signal_name,
                        proc.pid,
                        extra={
                            "download": {
                                "download_id": self.download_id,
                                "process_id": proc.pid,
                                "signal": signal_name,
                            }
                        },
                    )
                    os.kill(proc.pid, signal.SIGUSR1)

                    if wait_for_process_with_timeout(proc, 5):
                        self.logger.debug(
                            "Download process PID=%s stopped gracefully.",
                            proc.pid,
                            extra={
                                "download": {
                                    "download_id": self.download_id,
                                    "process_id": proc.pid,
                                    "signal": signal_name,
                                }
                            },
                        )
                        return True
                    self.logger.warning(
                        "Download process PID=%s did not respond to %s; forcing termination.",
                        proc.pid,
                        signal_name,
                        extra={
                            "download": {
                                "download_id": self.download_id,
                                "process_id": proc.pid,
                                "signal": signal_name,
                                "force": True,
                            }
                        },
                    )

                except (OSError, AttributeError) as e:
                    self.logger.debug(
                        "Failed to send %s signal to download process PID=%s. %s",
                        signal_name,
                        proc.pid,
                        e,
                        extra={
                            "download": {
                                "download_id": self.download_id,
                                "process_id": proc.pid,
                                "signal": signal_name,
                                "exception_type": type(e).__name__,
                            }
                        },
                    )

            if proc.is_alive():
                self.logger.info(
                    "Terminating download process PID=%s.",
                    proc.pid,
                    extra={"download": {"download_id": self.download_id, "process_id": proc.pid, "force": True}},
                )
                proc.terminate()

                if not wait_for_process_with_timeout(proc, 1 if self.is_live else 2):
                    self.logger.warning(
                        "Download process PID=%s did not terminate; killing forcefully.",
                        proc.pid,
                        extra={"download": {"download_id": self.download_id, "process_id": proc.pid, "force": True}},
                    )
                    proc.kill()
                    wait_for_process_with_timeout(proc, 1)

            self.logger.info(
                "Download process PID=%s stopped.",
                proc.pid,
                extra={"download": {"download_id": self.download_id, "process_id": proc.pid}},
            )
            return True

        except Exception as e:
            self.logger.exception(
                f"Failed to stop download process PID={proc.pid if proc else None}, ident={procId}.",
                extra={
                    "download": {
                        "download_id": self.download_id,
                        "process_id": proc.pid if proc else None,
                        "process_ident": procId,
                        "is_live": self.is_live,
                        "exception_type": type(e).__name__,
                    }
                },
            )

        return False

    async def close(self) -> bool:
        """
        Close the download process and clean up resources.

        This method must be called to properly release resources.

        Returns:
            True if close was successful, False otherwise

        """
        if not self.started() or self.cancel_in_progress:
            return False

        self.cancel_in_progress = True
        proc = self.proc
        procId: int | None = proc.ident if proc else None

        if not procId:
            if proc:
                proc.close()
                self.proc = None
            self.logger.warning("Attempted to close download process, but it is not running.")
            return False

        self.logger.info(
            "Closing download process PID='%s'.",
            procId,
            extra={"download": {"download_id": self.download_id, "process_ident": procId, "is_live": self.is_live}},
        )

        try:
            self.kill()

            import asyncio

            loop = asyncio.get_running_loop()

            current = self.proc
            if current is not None and current.is_alive():
                self.logger.debug(
                    "Waiting for download process PID='%s' to close.",
                    procId,
                    extra={"download": {"download_id": self.download_id, "process_ident": procId}},
                )
                await loop.run_in_executor(None, current.join)
                self.logger.debug(
                    "Download process PID='%s' closed.",
                    procId,
                    extra={"download": {"download_id": self.download_id, "process_ident": procId}},
                )

            if self.proc:
                self.proc.close()
                self.proc = None

            self.logger.debug(
                "Closed download process PID='%s'.",
                procId,
                extra={"download": {"download_id": self.download_id, "process_ident": procId}},
            )
            return True

        except Exception as e:
            self.logger.exception(
                f"Failed to close download process PID='{procId}'.",
                extra={
                    "download": {
                        "download_id": self.download_id,
                        "process_id": self.proc.pid if self.proc else None,
                        "process_ident": procId,
                        "is_live": self.is_live,
                        "exception_type": type(e).__name__,
                    }
                },
            )

        return False
