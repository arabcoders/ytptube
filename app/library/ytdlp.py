from __future__ import annotations

from typing import Any

import yt_dlp

import app.postprocessors  # noqa: F401


class YTDLP(yt_dlp.YoutubeDL):
    _interrupted = False

    def _delete_downloaded_files(self, *args, **kwargs):
        if self._interrupted:
            self.to_screen("[info] Cancelled — skipping temp cleanup.")
            return None

        return super()._delete_downloaded_files(*args, **kwargs)


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
            if (
                (getattr(opt, "_short_opts", []) or getattr(opt, "_long_opts", []))
                and getattr(opt, "help", None)
                and "SUPPRESSHELP" not in getattr(opt, "help", "")
            )
        ]

    return collect(parser.option_list, "root") + [
        entry for grp in parser.option_groups for entry in collect(grp.option_list, grp.title or "other")
    ]
