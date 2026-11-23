from pathlib import Path
from types import SimpleNamespace

import pytest

from app.routes.api import docs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name", ["CONTRIBUTING.md", "docs/authentication.md", "docs/media-handlers.md", "docs/toolbox.md"]
)
async def test_serves_doc(tmp_path: Path, name: str) -> None:
    (tmp_path / "README.md").write_text("root", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / name).write_text(name, encoding="utf-8")
    config = SimpleNamespace(app_path=str(tmp_path / "app"))
    request = SimpleNamespace(match_info={"file": name}, path=f"/api/docs/{name}")

    response = await docs.get_doc(request, config)

    assert response.status == 200
    assert response.content_type == "text/markdown"
    assert response.body == name.encode()


@pytest.mark.asyncio
async def test_rejects_unknown_doc(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("root", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    config = SimpleNamespace(app_path=str(tmp_path / "app"))
    request = SimpleNamespace(match_info={"file": "../README.md"}, path="/api/docs/../README.md")

    response = await docs.get_doc(request, config)

    assert response.status == 404
