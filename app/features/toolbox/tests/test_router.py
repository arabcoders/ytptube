from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.features.auth.middleware import auth_middleware
from app.features.auth.service import AuthService
from app.features.core.models import utcnow
from app.features.toolbox import router
from app.features.toolbox.defaults import REMUX
from app.features.toolbox.schemas import Result
from app.features.toolbox.service import Toolbox
from app.features.toolbox.tests import REMUX_ID, patch_tool
from app.library.config import Config, ExternalAuthConfig, RemoteUserConfig
from app.library.HttpAPI import HttpAPI
from app.library.Services import Services


@pytest.fixture
def http_api(toolbox: Toolbox, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[HttpAPI]:
    services = Services.get_instance()
    with monkeypatch.context() as patch:
        patch.setattr(services, "_services", [])
        services.add("toolbox", toolbox)
        patch.setattr(Config, "get_instance", lambda: toolbox.config)
        yield HttpAPI(tmp_path)


@pytest.mark.asyncio
async def test_tools_dispatch(http_api: HttpAPI) -> None:
    response = await http_api._handle(router.tools_list, make_mocked_request("GET", "/api/toolbox/tools"))
    assert isinstance(response, web.Response) and response.text is not None
    assert response.status == 200
    items = json.loads(response.text)["items"]
    assert {item["id"] for item in items} == {REMUX_ID}
    assert all(item["available"] and item["options_schema"] for item in items)
    assert items[0]["options_schema"]["properties"] == {}


@pytest.mark.asyncio
async def test_definitions_crud(http_api: HttpAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    async def call(
        handler: Callable[..., Awaitable[web.Response]],
        method: str,
        identifier: int | None = None,
        data: dict | None = None,
        query: str = "",
    ) -> tuple[int, dict]:
        path = "/api/toolbox/definitions/"
        request = (
            make_mocked_request(method, f"{path}{identifier}", match_info={"id": str(identifier)})
            if identifier is not None
            else make_mocked_request(method, f"{path}{query}")
        )
        if data is not None:
            monkeypatch.setattr(request, "json", AsyncMock(return_value=data))
        response = await http_api._handle(handler, request)
        assert isinstance(response, web.Response)
        return response.status, json.loads(response.text) if response.text else {}

    spec = {"name": "Copy", "command": ["ffmpeg"], "env": {"MODE": "fixed"}, "output_extension": ".mkv"}
    status, created = await call(router.definitions_add, "POST", data=spec)
    identifier = created["id"]
    assert status == 201 and type(identifier) is int and identifier != REMUX_ID and not created["default"]
    assert (await call(router.definitions_add, "POST", data={**spec, "id": identifier}))[0] == 400
    assert (await call(router.definitions_add, "POST", data={**spec, "default": True}))[0] == 400

    status, listing = await call(router.definitions_list, "GET")
    assert status == 200 and listing["pagination"]["total"] == 1
    custom = {"id": identifier, "name": "Copy", "description": "", "default": False}
    assert listing["items"] == [custom]

    status, listing = await call(router.definitions_list, "GET", query="?include_defaults=true")
    assert status == 200 and listing["pagination"]["total"] == 2
    assert listing["items"] == [
        {
            "id": REMUX_ID,
            "name": "Remux into MP4",
            "description": "Copy streams into MP4 without re-encoding.",
            "default": True,
        },
        custom,
    ]
    status, first = await call(router.definitions_list, "GET", query="?per_page=1")
    assert status == 200 and first["pagination"]["total_pages"] == 1 and first["items"] == [custom]
    status, second = await call(router.definitions_list, "GET", query="?include_defaults=true&per_page=1&page=2")
    assert status == 200 and second["pagination"]["total_pages"] == 2 and second["items"] == [custom]

    status, shipped = await call(router.definitions_get, "GET", REMUX_ID)
    assert status == 200 and shipped["default"] and shipped["command"] == REMUX.command
    updated = {**spec, "name": "New name"}
    assert (await call(router.definitions_replace, "PUT", REMUX_ID, updated))[0] == 409
    assert (await call(router.definitions_delete, "DELETE", REMUX_ID))[0] == 409
    assert (await call(router.definitions_replace, "PUT", identifier, updated))[0] == 200
    status, item = await call(router.definitions_get, "GET", identifier)
    assert status == 200 and item["name"] == "New name" and item["env"] == {"MODE": "fixed"}
    status, catalog = await call(router.tools_list, "GET")
    assert status == 200 and next(item for item in catalog["items"] if item["id"] == identifier)["name"] == "New name"
    assert (await call(router.definitions_delete, "DELETE", identifier))[0] == 204
    assert (await call(router.definitions_get, "GET", identifier))[0] == 404
    status, copied = await call(router.definitions_add, "POST", data=spec)
    assert status == 201 and copied["id"] != identifier

    draft = {key: value for key, value in shipped.items() if key not in {"id", "default"}}
    status, clone = await call(router.definitions_add, "POST", data=draft)
    assert status == 201 and not clone["default"] and clone["id"] != REMUX_ID
    assert clone["command"] == shipped["command"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("disabled", "status"), [(True, 403), (False, 401)])
async def test_definition_auth(toolbox: Toolbox, monkeypatch: pytest.MonkeyPatch, disabled: bool, status: int) -> None:
    config = toolbox.config
    config.disable_auth = disabled
    config.cors_origins = ""
    config.external_auth = ExternalAuthConfig(
        external_user=None,
        oidc=None,
        remote_user=RemoteUserConfig(enabled=False, header="Remote-User", trusted_proxies=()),
    )
    middleware = auth_middleware(AsyncMock(spec=AuthService), config)
    request = make_mocked_request("POST", "/api/toolbox/definitions/")
    monkeypatch.setattr(request.match_info.route, "name", "toolbox_definition_add")
    handler = AsyncMock()
    response = await middleware(request, handler)
    assert response.status == status
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_history(http_api: HttpAPI, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = source.parent / "tester/bar"
    folder.mkdir(parents=True)
    media = folder / "test.mp4"
    media.write_bytes(b"unrelated")
    file = "tester/bar/#360度ロック 🎵 #乃木坂46.mp4"
    request = make_mocked_request("POST", "/api/toolbox/jobs")
    monkeypatch.setattr(request, "json", AsyncMock(return_value={"tool": REMUX_ID, "file": file}))
    response = await http_api._handle(router.jobs_submit, request)
    assert isinstance(response, web.Response) and response.text is not None
    assert response.status == 404
    assert json.loads(response.text) == {
        "error": f"File '{file}' is no longer available.",
        "code": "FILE_UNAVAILABLE",
        "params": {"file": file},
    }
    assert media.read_bytes() == b"unrelated"


@pytest.mark.asyncio
@pytest.mark.parametrize("overwrite_source", [True, False])
@pytest.mark.parametrize("status", ["succeeded", "skipped"])
async def test_api_lifecycle(
    http_api: HttpAPI, source: Path, monkeypatch: pytest.MonkeyPatch, terminal, overwrite_source: bool, status: str
) -> None:
    patch_tool(
        monkeypatch,
        execute=AsyncMock(return_value=Result()),
        pre=AsyncMock(return_value="Nothing to do.") if status == "skipped" else None,
    )
    request = make_mocked_request("POST", "/api/toolbox/jobs")
    data = {"tool": REMUX_ID, "file": source.name}
    if not overwrite_source:
        data["extra"] = {"overwrite_source": False, "options": {}}
    monkeypatch.setattr(request, "json", AsyncMock(return_value=data))
    accepted = await http_api._handle(router.jobs_submit, request)
    assert isinstance(accepted, web.Response) and accepted.text is not None
    assert accepted.status == 202
    job = json.loads(accepted.text)
    assert isinstance(job["id"], int) and job["id"] > 0
    assert job["status"] == "queued" and job["file"] == source.name
    assert job["extra"] == {"overwrite_source": overwrite_source, "options": {}}
    await terminal(job["id"])
    path = f"/api/toolbox/jobs/{job['id']}"
    request = make_mocked_request("GET", path, match_info={"id": str(job["id"])})
    response = await http_api._handle(router.jobs_get, request)
    assert isinstance(response, web.Response) and response.text is not None
    assert response.status == 200 and json.loads(response.text)["status"] == status
    assert json.loads(response.text)["extra"] == {"overwrite_source": overwrite_source, "options": {}}
    response = await http_api._handle(
        router.jobs_list, make_mocked_request("GET", f"/api/toolbox/jobs?status={status}")
    )
    assert isinstance(response, web.Response) and response.text is not None
    assert response.status == 200 and json.loads(response.text)["items"][0]["id"] == job["id"]
    assert json.loads(response.text)["items"][0]["extra"] == {"overwrite_source": overwrite_source, "options": {}}
    response = await http_api._handle(
        router.jobs_cancel, make_mocked_request("POST", f"{path}/cancel", match_info={"id": str(job["id"])})
    )
    assert isinstance(response, web.Response) and response.text is not None
    assert response.status == 200 and json.loads(response.text)["status"] == status
    assert (
        await http_api._handle(
            router.jobs_delete, make_mocked_request("DELETE", path, match_info={"id": str(job["id"])})
        )
    ).status == 204
    assert (await http_api._handle(router.jobs_get, request)).status == 404


@pytest.mark.asyncio
async def test_list_snapshot(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    job = await toolbox.repo.create(
        {"tool": REMUX_ID, "file": source.name, "status": "succeeded", "created_at": utcnow()}
    )
    list_paginated = toolbox.repo.list_paginated

    async def list_deleted(page: int, per_page: int, status: str | None):
        result = await list_paginated(page, per_page, status)
        await toolbox.delete(job.id)
        return result

    monkeypatch.setattr(toolbox.repo, "list_paginated", list_deleted)
    response = await router.jobs_list(
        make_mocked_request("GET", "/api/toolbox/jobs?page=1&per_page=2&status=succeeded"), toolbox
    )
    data = json.loads(response.text)
    assert response.status == 200 and data["items"][0]["id"] == job.id
    assert data["pagination"] == {
        "page": 1,
        "per_page": 2,
        "total": 1,
        "total_pages": 1,
        "has_next": False,
        "has_prev": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        [],
        {"tool": REMUX_ID, "file": "video", "extra": True},
        {"tool": REMUX_ID, "file": "video", "extra": {"options": {"args": "-y"}}},
        {"tool": REMUX_ID, "file": "video", "extra": {"overwrite_source": "false"}},
        {"tool": REMUX_ID, "file": "video", "extra": {"overwrite_source": 0}},
        {"tool": 2**63, "file": "video"},
    ],
)
async def test_invalid_submission(toolbox: Toolbox, source: Path, body: object) -> None:
    request = MagicMock(spec=web.Request)
    request.json = AsyncMock(return_value=body)
    response = await router.jobs_submit(request, toolbox)
    assert response.status == 400 and json.loads(response.text)["code"] == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_invalid_status(toolbox: Toolbox) -> None:
    response = await router.jobs_list(make_mocked_request("GET", "/api/toolbox/jobs?status=bogus"), toolbox)
    assert response.status == 400
    assert json.loads(response.text)["params"] == {"field": "api.fields.status"}


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["not-an-id", "1.5", str(2**63)])
@pytest.mark.parametrize(
    ("handler", "method", "suffix"),
    [(router.jobs_get, "GET", ""), (router.jobs_cancel, "POST", "/cancel"), (router.jobs_delete, "DELETE", "")],
)
async def test_invalid_id(http_api: HttpAPI, handler, method: str, suffix: str, identifier: str) -> None:
    request = make_mocked_request(method, f"/api/toolbox/jobs/{identifier}{suffix}", match_info={"id": identifier})
    response = await http_api._handle(handler, request)
    assert response.status == 400
