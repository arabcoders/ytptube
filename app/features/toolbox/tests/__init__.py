from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from app.features.toolbox import service
from app.features.toolbox.definitions import SavedDefinition
from app.features.toolbox.tools import Tool, configured

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


REMUX_ID = 1


def patch_tool(monkeypatch: pytest.MonkeyPatch, **changes: Any) -> None:
    def configure(spec: SavedDefinition, config_dir: Path) -> Tool:
        tool = configured(spec, config_dir)
        return replace(tool, **changes) if spec.id == REMUX_ID else tool

    monkeypatch.setattr(service, "configured", configure)
