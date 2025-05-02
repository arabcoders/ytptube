#!/usr/bin/env python3

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

import caribou
import magic
from aiohttp import web
from library.config import Config
from library.DownloadQueue import DownloadQueue
from library.Events import EventBus, Events
from library.HttpAPI import HttpAPI
from library.HttpSocket import HttpSocket
from library.Notifications import Notification
from library.Presets import Presets
from library.Scheduler import Scheduler
from library.Tasks import Tasks

LOG = logging.getLogger("app")
MIME = magic.Magic(mime=True)

# Monkey patch yt-dlp to fix live_from_start mpd issues

from yt_dlp.extractor.youtube import YoutubeIE


def _patched_prepare_live_from_start_formats(
    self, formats, video_id, live_start_time, url, webpage_url, smuggled_data, is_live
):
    import functools
    import threading
    import time

    from yt_dlp.utils import LazyList, bug_reports_message, traverse_obj

    lock = threading.Lock()
    start_time = time.time()
    formats = [f for f in formats if f.get("is_from_start")]

    def refetch_manifest(format_id, delay):  # noqa: ARG001
        nonlocal formats, start_time, is_live
        if time.time() <= start_time + delay:
            return
        # re-download player responses & re-list formats
        _, _, prs, player_url = self._download_player_responses(url, smuggled_data, video_id, webpage_url)
        video_details = traverse_obj(prs, (..., "videoDetails"), expected_type=dict)
        microformats = traverse_obj(prs, (..., "microformat", "playerMicroformatRenderer"), expected_type=dict)
        _, live_status, _, formats, _ = self._list_formats(video_id, microformats, video_details, prs, player_url)
        is_live = live_status == "is_live"
        start_time = time.time()

    def mpd_feed(format_id, delay):
        """
        @returns (manifest_url, manifest_stream_number, is_live) or None
        """
        for retry in self.RetryManager(fatal=False):
            with lock:
                refetch_manifest(format_id, delay)

            # only pick formats that actually have a manifest_url
            f = next((f for f in formats if f.get("format_id") == format_id and "manifest_url" in f), None)
            if not f:
                if "manifest_url" not in f:
                    retry.error = f"{video_id}: In post manifest-less mode."
                elif not is_live:
                    retry.error = f"{video_id}: Video is no longer live"
                else:
                    retry.error = f"Cannot find refreshed manifest for format {format_id}{bug_reports_message()}"
                continue
            return f.get("manifest_url"), f.get("manifest_stream_number"), is_live
        return None

    for f in formats:
        f["is_live"] = is_live
        gen = functools.partial(
            self._live_dash_fragments,
            video_id,
            f.get("format_id"),
            live_start_time,
            mpd_feed,
            (not is_live) and f.copy(),
        )
        if is_live:
            f["fragments"] = gen
            f["protocol"] = "http_dash_segments_generator"
        else:
            f["fragments"] = LazyList(gen({}))
            f.pop("is_from_start", None)


YoutubeIE._prepare_live_from_start_formats = _patched_prepare_live_from_start_formats
# End


class Main:
    def __init__(self):
        self._config = Config.get_instance()
        self.rootPath = str(Path(__file__).parent.absolute())
        self._app = web.Application()

        self._check_folders()

        caribou.upgrade(self._config.db_file, os.path.join(self.rootPath, "migrations"))

        connection = sqlite3.connect(database=self._config.db_file, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=wal")

        async def _close_connection(_):
            LOG.debug("Closing database connection.")
            connection.close()
            LOG.debug("Database connection closed.")

        try:
            if "600" != oct(os.stat(self._config.db_file).st_mode)[-3:]:
                os.chmod(self._config.db_file, 0o600)
        except Exception:
            pass

        self._queue = DownloadQueue(connection=connection)
        self._http = HttpAPI(queue=self._queue)
        self._socket = HttpSocket(queue=self._queue)

        self._app.on_cleanup.append(_close_connection)

    def _check_folders(self):
        """Check if the required folders exist and create them if they do not."""
        folders = (self._config.download_path, self._config.temp_path, self._config.config_path)

        for folder in folders:
            try:
                LOG.debug(f"Checking folder at '{folder}'.")
                if not os.path.exists(folder):
                    LOG.info(f"Creating folder at '{folder}'.")
                    os.makedirs(folder, exist_ok=True)
            except OSError:
                LOG.error(f"Could not create folder at '{folder}'.")
                raise

        try:
            LOG.debug(f"Checking database file at '{self._config.db_file}'.")
            if not os.path.exists(self._config.db_file):
                LOG.info(f"Creating database file at '{self._config.db_file}'.")
                with open(self._config.db_file, "w") as _:
                    pass
        except OSError:
            LOG.error(f"Could not create database file at '{self._config.db_file}'.")
            raise

    def start(self):
        """
        Start the application.
        """
        EventBus.get_instance().sync_emit(Events.STARTUP, data={"app": self._app})

        Scheduler.get_instance().attach(self._app)

        self._socket.attach(self._app)
        self._http.attach(self._app)
        self._queue.attach(self._app)

        Tasks.get_instance().attach(self._app)
        Presets.get_instance().attach(self._app)
        Notification.get_instance().attach(self._app)

        EventBus.get_instance().sync_emit(Events.LOADED, data={"app": self._app})

        def started(_):
            LOG.info("=" * 40)
            LOG.info(f"YTPTube v{self._config.version} - started on http://{self._config.host}:{self._config.port}")
            LOG.info("=" * 40)

        HTTP_LOGGER = None
        if self._config.access_log:
            from library.HttpAPI import LOG as HTTP_LOGGER

            HTTP_LOGGER.addFilter(lambda record: "GET /api/ping" not in record.getMessage())

        web.run_app(
            self._app,
            host=self._config.host,
            port=self._config.port,
            reuse_port=True,
            loop=asyncio.get_event_loop(),
            access_log=HTTP_LOGGER,
            print=started,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    Main().start()
