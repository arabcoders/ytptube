import logging
import subprocess
import sys
from typing import Any

LOG: logging.Logger = logging.getLogger("ytdlp.utils")


def patch_metadataparser() -> None:
    """
    Patches yt_dlp MetadataParserPP action to handle subprocess pickling issues.
    """
    try:
        from yt_dlp.postprocessor.metadataparser import MetadataParserPP
        from yt_dlp.utils import Namespace
    except Exception as exc:
        LOG.warning(f"Unable to import yt_dlp metadata parser for patching: {exc!s}")
        return

    if getattr(MetadataParserPP.Actions, "_ytptube_patched", False):
        return

    class _ActionNS(Namespace):
        _ACTIONS_STR: list[str] = []

        @staticmethod
        def _get_name(func) -> str | None:
            if not callable(func):
                return None

            target = getattr(func, "__func__", func)
            module_name = getattr(target, "__module__", None)
            qual_name = getattr(target, "__qualname__", getattr(target, "__name__", None))

            return f"{module_name}.{qual_name}" if module_name and qual_name else None

        def __contains__(self, candidate: object) -> bool:
            if candidate in self.__dict__.values():
                return True

            if func_name := _ActionNS._get_name(candidate):
                if len(_ActionNS._ACTIONS_STR) < 1:
                    _ActionNS._ACTIONS_STR.extend(
                        [value for value in (_ActionNS._get_name(value) for value in self.__dict__.values()) if value]
                    )

                return func_name in _ActionNS._ACTIONS_STR

            return False

    actions_dict: dict[str, Any] = dict(MetadataParserPP.Actions.items_)
    MetadataParserPP.Actions = _ActionNS(**actions_dict)
    MetadataParserPP.Actions._ytptube_patched = True
    LOG.debug("MetadataParserPP action namespace patch applied successfully.")


def patch_windows_popen_wait() -> None:
    if sys.platform != "win32":
        return

    try:
        from yt_dlp.utils import Popen
    except Exception as exc:
        LOG.warning(f"Unable to import yt_dlp Popen for patching: {exc!s}")
        return

    if getattr(Popen, "_ytptube_wait_patched", False):
        return

    original_wait = Popen.wait

    # Windows subprocess waits can swallow the synthetic interrupt we use to
    # stop live downloads, especially while yt-dlp is blocked on ffmpeg.
    def interruptible_wait(self, timeout=None):
        if timeout is not None:
            return original_wait(self, timeout=timeout)

        while True:
            try:
                return original_wait(self, timeout=0.1)
            except subprocess.TimeoutExpired:
                continue

    Popen.wait = interruptible_wait
    Popen._ytptube_wait_patched = True
    LOG.debug("yt_dlp Popen.wait Windows patch applied successfully.")


def apply_ytdlp_patches() -> None:
    try:
        patch_metadataparser()
    except Exception as exc:
        LOG.debug("Metadata parser patch failed to apply: %s", exc)

    try:
        patch_windows_popen_wait()
    except Exception as exc:
        LOG.debug("Windows Popen wait patch failed to apply: %s", exc)
