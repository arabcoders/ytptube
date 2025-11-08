"""
Patches yt_dlp.postprocessor.metadataparser.MetadataParserPP action namespace to handle duplicated class objects.

This patch is necessary due to to how we parse yt-dlp cli options. on top fo that we have pickling issue as well.
So we need to compare callables structurally rather than by identity as the identity may differ across instances.
"""

from __future__ import annotations

import logging
from typing import Any

LOG: logging.Logger = logging.getLogger(__name__)


def _callable_fingerprint(func: object) -> tuple[Any, ...] | None:
    if not callable(func):
        return None

    target = getattr(func, "__func__", func)
    code = getattr(target, "__code__", None)
    defaults = getattr(target, "__defaults__", None)
    kwdefaults = getattr(target, "__kwdefaults__", None)

    return (
        getattr(target, "__module__", None),
        getattr(target, "__qualname__", getattr(target, "__name__", None)),
        getattr(code, "co_code", None),
        getattr(code, "co_consts", None),
        defaults,
        kwdefaults,
    )


def ensure_patch() -> None:
    try:
        from yt_dlp.postprocessor.metadataparser import MetadataParserPP
        from yt_dlp.utils import Namespace
    except Exception as exc:
        LOG.warning(f"Unable to import yt_dlp metadata parser for patching: {exc!s}")
        return

    if getattr(MetadataParserPP.Actions, "_ytptube_patched", False):
        return

    class _ActionNamespace(Namespace):
        def __contains__(self, candidate: object) -> bool:
            if candidate in self.__dict__.values():
                return True

            candidate_fp = _callable_fingerprint(candidate)
            if candidate_fp is None:
                return False

            return any(_callable_fingerprint(value) == candidate_fp for value in self.__dict__.values())

    actions_dict = dict(MetadataParserPP.Actions.items_)
    MetadataParserPP.Actions = _ActionNamespace(**actions_dict)
    MetadataParserPP.Actions._ytptube_patched = True
    LOG.debug("MetadataParserPP action namespace patch applied successfully.")
