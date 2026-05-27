"""Temporary file and directory management for downloads."""

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.library.Utils import delete_dir

from .utils import is_safe_to_delete_dir

if TYPE_CHECKING:
    from app.library.ItemDTO import ItemDTO


class TempManager:
    def __init__(
        self,
        info: "ItemDTO",
        temp_dir: str | None,
        temp_disabled: bool,
        temp_keep: bool,
        logger: logging.Logger,
    ):
        """
        Initialize temp manager.

        Args:
            info: Download information object
            temp_dir: Base temporary directory path
            temp_disabled: Whether temporary directory feature is disabled
            temp_keep: Whether to keep temp files after download
            logger: Logger instance

        """
        self.info = info
        self.temp_dir = temp_dir
        self.temp_disabled = temp_disabled
        self.temp_keep = temp_keep
        self.logger = logger
        self.temp_path: Path | None = None

    def create_temp_path(self) -> Path | None:
        """
        Create unique temporary directory for this download.

        Returns:
            Path to created temporary directory, or None if disabled

        """
        if self.temp_disabled or not self.temp_dir:
            return None

        self.temp_path = Path(self.temp_dir) / hashlib.shake_256(f"D-{self.info.id}".encode()).hexdigest(5)

        if not self.temp_path.exists():
            self.temp_path.mkdir(parents=True, exist_ok=True)

        return self.temp_path

    def delete_temp(self, by_pass: bool = False) -> None:
        """
        Delete temporary directory if conditions are met.

        Temp directory is kept if:
        - temp_keep is enabled
        - temp_disabled is enabled
        - Download hasn't finished but has partial data (unless by_pass=True)

        Args:
            by_pass: Force deletion regardless of download state

        """
        if self.temp_disabled or self.temp_keep is True or not self.temp_path:
            return

        if (
            not by_pass
            and "finished" != self.info.status
            and self.info.downloaded_bytes
            and self.info.downloaded_bytes > 0
        ):
            self.logger.warning(
                "Keeping temp folder '%s' for unfinished download '%s'.",
                self.temp_path,
                self.info.title,
                extra={
                    "download": {
                        "download_id": self.info._id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "temp_path": str(self.temp_path),
                        "status": self.info.status,
                    }
                },
            )
            return

        tmp_dir = Path(self.temp_path)

        if not tmp_dir.exists():
            return

        if not self.temp_dir or not is_safe_to_delete_dir(tmp_dir, self.temp_dir):
            self.logger.warning(
                "Refusing to delete temp folder '%s' for '%s' because it is not safe.",
                self.temp_path,
                self.info.title,
                extra={
                    "download": {
                        "download_id": self.info._id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "temp_path": str(self.temp_path),
                        "temp_dir": self.temp_dir,
                    }
                },
            )
            return

        status: bool = delete_dir(tmp_dir)
        if by_pass:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(
                "Emptied temp folder '%s' for '%s'.",
                self.temp_path,
                self.info.title,
                extra={
                    "download": {
                        "download_id": self.info._id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "temp_path": str(self.temp_path),
                    }
                },
            )
        else:
            self.logger.info(
                "Temp folder '%s' deletion for '%s' %s.",
                self.temp_path,
                self.info.title,
                "succeeded" if status else "failed",
                extra={
                    "download": {
                        "download_id": self.info._id,
                        "item_id": self.info.id,
                        "title": self.info.title,
                        "temp_path": str(self.temp_path),
                        "deleted": status,
                    }
                },
            )
