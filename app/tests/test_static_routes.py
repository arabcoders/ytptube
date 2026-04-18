from pathlib import Path
from typing import Generator

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.library.config import Config
from app.library.router import ROUTES
from app.routes.api import _static


@pytest.fixture(autouse=True)
def reset_static_routes() -> Generator[None, None, None]:
    Config._reset_singleton()
    ROUTES.clear()
    _static.STATIC_STATE.root = None
    _static.STATIC_STATE.index_file = None
    yield
    _static.STATIC_STATE.root = None
    _static.STATIC_STATE.index_file = None
    ROUTES.clear()
    Config._reset_singleton()


def _make_request(path: str, *, accept: str = "text/html") -> web.Request:
    return make_mocked_request("GET", path, headers={"Accept": accept})


def _configure_static_root(static_root: Path) -> None:
    _static.STATIC_STATE.root = static_root.resolve()
    _static.STATIC_STATE.index_file = (_static.STATIC_STATE.root / "index.html").resolve()


class TestServeStaticFile:
    @pytest.mark.asyncio
    async def test_nested_document_route_falls_back_to_spa_shell(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        index_file = tmp_path / "index.html"
        index_file.write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)

        response = await _static.serve_static_file(_make_request("/docs/readme"), config)

        assert isinstance(response, web.FileResponse)
        assert response._path == index_file

    @pytest.mark.asyncio
    async def test_generated_nested_index_is_not_preferred_over_root_shell(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        root_index = tmp_path / "index.html"
        nested_index = tmp_path / "docs" / "readme" / "index.html"
        nested_index.parent.mkdir(parents=True)
        root_index.write_text("<html>root shell</html>", encoding="utf-8")
        nested_index.write_text("<html>nested shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)

        response = await _static.serve_static_file(_make_request("/docs/readme"), config)

        assert isinstance(response, web.FileResponse)
        assert response._path == root_index

    @pytest.mark.asyncio
    async def test_missing_asset_does_not_fall_back(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _configure_static_root(tmp_path)

        request = make_mocked_request(
            "GET",
            "/assets/missing.js",
            headers={"Accept": "*/*", "Sec-Fetch-Dest": "script"},
        )
        response = await _static.serve_static_file(request, config)

        assert isinstance(response, web.Response)
        body = response.body
        assert isinstance(body, bytes)
        assert response.status == web.HTTPNotFound.status_code
        assert b"missing.js" in body

    @pytest.mark.asyncio
    async def test_missing_asset_with_unknown_suffix_does_not_fall_back(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _configure_static_root(tmp_path)

        request = make_mocked_request(
            "GET",
            "/assets/missing.abcd123",
            headers={"Accept": "*/*", "Sec-Fetch-Dest": "script"},
        )
        response = await _static.serve_static_file(request, config)

        assert isinstance(response, web.Response)
        body = response.body
        assert isinstance(body, bytes)
        assert response.status == web.HTTPNotFound.status_code
        assert b"missing.abcd123" in body

    @pytest.mark.asyncio
    async def test_symlink_outside_static_root_does_not_resolve(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        outside_dir = tmp_path.parent / "outside-static-root"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "secret.js"
        outside_file.write_text("console.log('outside')", encoding="utf-8")
        try:
            (tmp_path / "leak.js").symlink_to(outside_file)
            _configure_static_root(tmp_path)

            response = await _static.serve_static_file(_make_request("/leak.js"), config)

            assert isinstance(response, web.Response)
            body = response.body
            assert isinstance(body, bytes)
            assert response.status == web.HTTPNotFound.status_code
            assert b"/leak.js" in body
        finally:
            if (tmp_path / "leak.js").exists() or (tmp_path / "leak.js").is_symlink():
                (tmp_path / "leak.js").unlink()
            if outside_file.exists():
                outside_file.unlink()
            if outside_dir.exists():
                outside_dir.rmdir()

    @pytest.mark.asyncio
    async def test_missing_api_path_does_not_fall_back(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)

        response = await _static.serve_static_file(_make_request("/api/missing"), config)

        assert isinstance(response, web.Response)
        body = response.body
        assert isinstance(body, bytes)
        assert response.status == web.HTTPNotFound.status_code
        assert b"/api/missing" in body

    @pytest.mark.asyncio
    async def test_dotted_browser_path_returns_not_found(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)

        response = await _static.serve_static_file(_make_request("/browser/foo/bar.txt"), config)

        assert isinstance(response, web.Response)
        body = response.body
        assert isinstance(body, bytes)
        assert response.status == web.HTTPNotFound.status_code
        assert b"/browser/foo/bar.txt" in body

    def test_registers_only_root_and_catch_all_routes(self, tmp_path: Path) -> None:
        config = Config.get_instance()
        static_root = tmp_path / "ui-exported"
        static_root.mkdir()
        (static_root / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        (static_root / "assets").mkdir()
        (static_root / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

        config.static_ui_path = str(static_root)

        _static.setup_static_routes(tmp_path, config)

        http_routes = ROUTES.get("http", {})
        assert "index" in http_routes
        assert "static_fallback" in http_routes
        assert "/assets/app.js" not in {route.path for route in http_routes.values()}
