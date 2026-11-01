from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from app.features.core.models import utcnow
from app.features.toolbox import router, tools
from app.features.toolbox.schemas import Result
from app.features.toolbox.service import Toolbox
from app.library.config import Config
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
    assert {item["id"] for item in items} == {"remux"}
    assert all(item["available"] and item["options_schema"] for item in items)
    assert items[0]["options_schema"]["properties"] == {}


@pytest.mark.asyncio
async def test_missing_history(http_api: HttpAPI, source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = source.parent / "tester/bar"
    folder.mkdir(parents=True)
    media = folder / "test.mp4"
    media.write_bytes(b"unrelated")
    file = "tester/bar/#360度ロック 🎵 #乃木坂46.mp4"
    request = make_mocked_request("POST", "/api/toolbox/jobs")
    monkeypatch.setattr(request, "json", AsyncMock(return_value={"tool": "remux", "file": file}))
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
    monkeypatch.setitem(
        tools.TOOLS,
        "remux",
        replace(
            tools.TOOLS["remux"],
            execute=AsyncMock(return_value=Result()),
            pre=AsyncMock(return_value="Nothing to do.") if status == "skipped" else None,
        ),
    )
    request = make_mocked_request("POST", "/api/toolbox/jobs")
    data = {"tool": "remux", "file": source.name}
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
        {"tool": "remux", "file": source.name, "status": "succeeded", "created_at": utcnow()}
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
        {"tool": "remux", "file": "video", "extra": True},
        {"tool": "remux", "file": "video", "extra": {"options": {"args": "-y"}}},
        {"tool": "remux", "file": "video", "extra": {"overwrite_source": "false"}},
        {"tool": "remux", "file": "video", "extra": {"overwrite_source": 0}},
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
