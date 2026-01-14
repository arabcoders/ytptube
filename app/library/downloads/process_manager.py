"""Process lifecycle management for downloads."""

import logging
import multiprocessing
import os
import signal
from collections.abc import Callable

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
        self.proc: multiprocessing.Process | None = None
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
        self.proc = multiprocessing.Process(name=f"download-{self.download_id}", target=target)
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

        Attempts graceful termination via SIGUSR1 signal first (POSIX only),
        then escalates to terminate() and finally kill() if needed.
        Live streams get shorter timeouts as they're more likely to be unresponsive.

        Returns:
            True if process was killed successfully, False otherwise

        """
        if not self.running():
            return False

        procId: int | None = self.proc.ident
        try:
            self.logger.info(f"Killing download process: PID={self.proc.pid}, ident={procId}.")

            if self.proc.pid and "posix" == os.name:
                try:
                    self.logger.debug(f"Sending SIGUSR1 signal to PID={self.proc.pid}.")
                    os.kill(self.proc.pid, signal.SIGUSR1)

                    if wait_for_process_with_timeout(self.proc, 2 if self.is_live else 5):
                        self.logger.debug(f"Process PID={self.proc.pid} terminated gracefully.")
                        return True
                    self.logger.warning(
                        f"Process PID={self.proc.pid} did not respond to SIGUSR1 "
                        f"({'live stream' if self.is_live else 'regular download'}), "
                        f"forcing termination."
                    )

                except (OSError, AttributeError) as e:
                    self.logger.debug(f"Failed to send SIGUSR1 signal: {e}")

            if self.proc.is_alive():
                self.logger.info(f"Force-terminating process PID={self.proc.pid}.")
                self.proc.terminate()

                if not wait_for_process_with_timeout(self.proc, 1 if self.is_live else 2):
                    self.logger.warning(f"Process PID={self.proc.pid} did not respond, killing forcefully.")
                    self.proc.kill()
                    wait_for_process_with_timeout(self.proc, 1)

            self.logger.info(f"Process PID={self.proc.pid} killed.")
            return True

        except Exception as e:
            self.logger.error(f"Failed to kill process PID={self.proc.pid}, ident={procId}. {e}")
            self.logger.exception(e)

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
        procId: int | None = self.proc.ident

        if not procId:
            if self.proc:
                self.proc.close()
                self.proc = None
            self.logger.warning("Attempted to close download process, but it is not running.")
            return False

        self.logger.info(f"Closing PID='{procId}' download process.")

        try:
            self.kill()

            import asyncio

            loop = asyncio.get_running_loop()

            if self.proc.is_alive():
                self.logger.debug(f"Waiting for PID='{procId}' to close.")
                await loop.run_in_executor(None, self.proc.join)
                self.logger.debug(f"PID='{procId}' closed.")

            if self.proc:
                self.proc.close()
                self.proc = None

            self.logger.debug(f"Closed PID='{procId}' download process.")
            return True

        except Exception as e:
            self.logger.error(f"Failed to close process: '{procId}'. {e}")
            self.logger.exception(e)

        return False
