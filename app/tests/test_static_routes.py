from pathlib import Path
from typing import Generator

import pytest

from app.library.config import Config
from app.library.router import ROUTES
from app.routes.api import _static
from app.tests.helpers import url_for


@pytest.fixture(autouse=True)
def reset_static_routes() -> Generator[None, None, None]:
    Config._reset_singleton()
    snapshot = {route_type: routes.copy() for route_type, routes in ROUTES.items()}
    ROUTES.clear()
    _static.STATIC_STATE.root = None
    _static.STATIC_STATE.index_file = None
    yield
    _static.STATIC_STATE.root = None
    _static.STATIC_STATE.index_file = None
    ROUTES.clear()
    ROUTES.update(snapshot)
    Config._reset_singleton()


def _configure_static_root(static_root: Path) -> None:
    _static.STATIC_STATE.root = static_root.resolve()
    _static.STATIC_STATE.index_file = (_static.STATIC_STATE.root / "index.html").resolve()


def _register_static_routes(static_root: Path, config: Config) -> None:
    config.static_ui_path = str(static_root)
    _static.setup_static_routes(static_root, config)


class TestServeStaticFile:
    @pytest.mark.asyncio
    async def test_nested_doc_falls_back(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        index_file = tmp_path / "index.html"
        index_file.write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="docs/readme"))

        assert response.status == 200
        assert await response.text() == "<html>root shell</html>"

    @pytest.mark.asyncio
    async def test_fingerprinted_icon_rewrites(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        icon = tmp_path / "images" / "favicon.png"
        icon.parent.mkdir()
        icon.write_bytes(b"canonical icon")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="apple-touch-icon.0123456789ab.png"))

        assert response.status == 200
        assert await response.read() == b"canonical icon"
        assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"

    @pytest.mark.asyncio
    async def test_html_revalidates(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="index.html"))

        assert response.status == 200
        assert response.headers["Cache-Control"] == "public, max-age=0, must-revalidate"

    @pytest.mark.asyncio
    async def test_nested_index_uses_root(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        root_index = tmp_path / "index.html"
        nested_index = tmp_path / "docs" / "readme" / "index.html"
        nested_index.parent.mkdir(parents=True)
        root_index.write_text("<html>root shell</html>", encoding="utf-8")
        nested_index.write_text("<html>nested shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="docs/readme"))

        assert response.status == 200
        assert await response.text() == "<html>root shell</html>"

    @pytest.mark.asyncio
    async def test_missing_asset_no_fallback(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(
            url_for("static_fallback", path="assets/missing.js"),
            headers={"Accept": "*/*", "Sec-Fetch-Dest": "script"},
        )
        body = await response.read()
        assert response.status == 404
        assert b'"code": "NOT_FOUND"' in body

    @pytest.mark.asyncio
    async def test_missing_unknown_no_fallback(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(
            url_for("static_fallback", path="assets/missing.abcd123"),
            headers={"Accept": "*/*", "Sec-Fetch-Dest": "script"},
        )
        body = await response.read()
        assert response.status == 404
        assert b'"code": "NOT_FOUND"' in body

    @pytest.mark.asyncio
    async def test_symlink_outside_rejected(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        outside_dir = tmp_path.parent / "outside-static-root"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "secret.js"
        outside_file.write_text("console.log('outside')", encoding="utf-8")
        try:
            (tmp_path / "leak.js").symlink_to(outside_file)
            _configure_static_root(tmp_path)
            _register_static_routes(tmp_path, config)

            async def handler(request):
                return await _static.serve_static_file(request, config)

            client = await test_client({"static_fallback": handler})
            response = await client.get(url_for("static_fallback", path="leak.js"))
            body = await response.read()
            assert response.status == 404
            assert b'"code": "NOT_FOUND"' in body
        finally:
            if (tmp_path / "leak.js").exists() or (tmp_path / "leak.js").is_symlink():
                (tmp_path / "leak.js").unlink()
            if outside_file.exists():
                outside_file.unlink()
            if outside_dir.exists():
                outside_dir.rmdir()

    @pytest.mark.asyncio
    async def test_missing_api_no_fallback(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="api/missing"))
        body = await response.read()
        assert response.status == 404
        assert b'"code": "NOT_FOUND"' in body

    @pytest.mark.asyncio
    async def test_dotted_browser_path_404(self, tmp_path: Path, test_client) -> None:
        config = Config.get_instance()
        (tmp_path / "index.html").write_text("<html>root shell</html>", encoding="utf-8")
        _configure_static_root(tmp_path)
        _register_static_routes(tmp_path, config)

        async def handler(request):
            return await _static.serve_static_file(request, config)

        client = await test_client({"static_fallback": handler})
        response = await client.get(url_for("static_fallback", path="browser/foo/bar.txt"))
        body = await response.read()
        assert response.status == 404
        assert b'"code": "NOT_FOUND"' in body

    def test_registers_root_routes(self, tmp_path: Path) -> None:
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
