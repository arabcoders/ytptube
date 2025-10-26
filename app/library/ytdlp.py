# flake8: noqa: F401
from typing import Any

import yt_dlp
from yt_dlp.utils import make_archive_id

import app.postprocessors


class _ArchiveProxy:
    """
    Proxy for yt-dlp's self.archive that delegates to our Archiver.

    Supports membership checks (`id in proxy`) and `.add(id)`.
    """

    def __init__(self, file: str | None):
        self._file: str | None = file
        "The archive file path."

    def __contains__(self, item: str) -> bool:
        if not self._file or not item:
            return False

        try:
            from app.library.Archiver import Archiver

            status: bool = item in Archiver.get_instance().read(self._file, [item])
            return status
        except Exception:
            return False

    def add(self, item: str) -> bool:
        if not self._file or not item:
            return False

        try:
            from app.library.Archiver import Archiver

            status: bool = Archiver.get_instance().add(self._file, [item])
            return status
        except Exception:
            return False

    def __bool__(self) -> bool:
        return bool(self._file)


class YTDLP(yt_dlp.YoutubeDL):
    _interrupted = False

    def __init__(self, params=None, auto_init=True):
        # Avoid yt-dlp preloading the archive file by stripping the param first
        orig_file = None
        patched_params = None
        if params is not None:
            try:
                orig_file: str | None = params.get("download_archive")
                patched_params: dict = dict(params)
                if "download_archive" in patched_params:
                    patched_params.pop("download_archive", None)
            except Exception:
                patched_params = params

        super().__init__(params=patched_params, auto_init=auto_init)

        # Restore param and replace upstream archive set with our proxy
        if orig_file is not None:
            try:
                self.params["download_archive"] = orig_file
            except Exception:
                pass

        self.archive = _ArchiveProxy(orig_file)

    def _delete_downloaded_files(self, *args, **kwargs) -> None:
        if self._interrupted:
            self.to_screen("[info] Cancelled — skipping temp cleanup.")
            return None

        return super()._delete_downloaded_files(*args, **kwargs)

    def record_download_archive(self, info_dict) -> None:
        if not self.params.get("download_archive"):
            return

        if not (archive_id := self._make_archive_id(info_dict)):
            return

        assert archive_id

        self.write_debug(f"Adding to archive: {archive_id}")
        self.archive.add(archive_id)
        old_archive_ids = info_dict.get("_old_archive_ids", [])
        if old_archive_ids and isinstance(old_archive_ids, list) and len(old_archive_ids) > 0:
            for old_id in old_archive_ids:
                if old_id == archive_id or not old_id.startswith("generic "):
                    continue

                self.write_debug(f"Adding to archive (old id): {old_id}")
                self.archive.add(old_id)


def ytdlp_options() -> list[dict[str, Any]]:
    """
    Collect yt-dlp options and return them in a structured format.

    Returns:
        list[dict[str, Any]]: A list of dictionaries containing option flags, descriptions,

    """
    from yt_dlp.options import create_parser

    from app.library.Utils import REMOVE_KEYS

    parser = create_parser()

    ignored_flags: set[str] = {
        f.strip() for group in REMOVE_KEYS for v in group.values() for f in v.split(",") if f.strip()
    }

    def collect(opts, group: str) -> list[dict[str, Any]]:
        return [
            {
                "flags": list(getattr(opt, "_short_opts", [])) + list(getattr(opt, "_long_opts", [])),
                "description": getattr(opt, "help", None),
                "group": group,
                "ignored": any(
                    f in ignored_flags for f in getattr(opt, "_short_opts", []) + getattr(opt, "_long_opts", [])
                ),
            }
            for opt in opts
            if (getattr(opt, "_long_opts", []) and getattr(opt, "help", None))
        ]

    opts = collect(parser.option_list, "root") + [
        entry for grp in parser.option_groups for entry in collect(grp.option_list, grp.title or "other")
    ]

    for opt in opts:
        if "SUPPRESSHELP" in opt.get("description", ""):
            opt["description"] = "No description available from yt-dlp."

    return opts
