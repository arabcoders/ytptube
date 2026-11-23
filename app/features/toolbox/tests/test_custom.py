from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp.test_utils import make_mocked_request

from app.features.toolbox import repository, router
from app.features.toolbox.definitions import Definition, SavedDefinition, ShippedDefinition
from app.features.toolbox.schemas import Extra, Result, Submission
from app.features.toolbox.service import Context, Toolbox
from app.features.toolbox.tests import REMUX_ID, patch_tool


@pytest_asyncio.fixture
async def definition(toolbox: Toolbox) -> SavedDefinition:
    spec = Definition.model_validate(
        {
            "name": "Convert",
            "command": [sys.executable],
            "output_extension": ".json",
            "env": {"WRAPPER_MODE": "fixed"},
            "params": {
                "LEVEL": {"default": 5, "min": 0, "max": 12},
                "FILTER": {"default": False},
                "GAIN": {"default": 1.0, "min": 0},
                "mode": {"default": "fast", "choices": ["fast", "high quality"]},
            },
        }
    )
    return await toolbox.definitions.create(spec)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [{}, {"overwrite_source": True, "options": {"LEVEL": 8, "FILTER": True, "GAIN": 1.5, "mode": "high quality"}}],
)
async def test_custom_invocation(
    toolbox: Toolbox,
    source: Path,
    definition: SavedDefinition,
    terminal,
    monkeypatch: pytest.MonkeyPatch,
    extra: dict,
) -> None:
    script = source.with_name("my wrapper.py")
    script.write_text(
        """import json, os, sys
from pathlib import Path
output = Path(os.environ["TB_OUT"])
output.write_text(json.dumps({
    "args": sys.argv[1:],
    "cwd": str(Path.cwd()),
    "stdin": sys.stdin.read(),
    "env": {key: os.environ[key] for key in (
        "TB_IN", "TB_OUT", "INHERITED", "WRAPPER_MODE", "LEVEL", "FILTER", "GAIN", "mode"
    )},
}), encoding="utf-8")
print("stderr diagnostic", file=sys.stderr)
""",
        encoding="utf-8",
    )
    source = source.rename(source.with_name("Episode 日本語 #1.mp4"))
    monkeypatch.setenv("INHERITED", "inherited")
    monkeypatch.setenv("WRAPPER_MODE", "server default")
    literal = '{"key":"literal argument with spaces"}'
    spec = Definition.model_validate(
        {
            **definition.model_dump(exclude={"id", "default"}),
            "command": [sys.executable, str(script), "{input}", "{output}", "{param.mode}", literal],
            "output_extension": ".data.long-extension",
        }
    )
    assert await toolbox.definitions.replace(definition.id, spec)

    params = Extra.model_validate(extra)
    accepted = await toolbox.submit(Submission(tool=definition.id, file=source.name, extra=params))
    job = await terminal(accepted.id)
    assert job.status == "succeeded", (job.error, job.log)
    assert not job.extra.overwrite_source
    assert job.extra.options == {"LEVEL": 5, "FILTER": False, "GAIN": 1.0, "mode": "fast", **params.options}
    relative = f"{source.stem}.tool-{definition.id}.data.long-extension"
    assert job.result and job.result.outputs == [relative]
    data = json.loads((source.parent / relative).read_text(encoding="utf-8"))
    output = Path(data["env"]["TB_OUT"])
    assert data["args"] == [str(source), str(output), job.extra.options["mode"], literal]
    assert data["cwd"] == str(output.parent) and data["stdin"] == ""
    assert data["env"] == {
        "TB_IN": str(source),
        "TB_OUT": str(output),
        "INHERITED": "inherited",
        "WRAPPER_MODE": "fixed",
        "LEVEL": str(job.extra.options["LEVEL"]),
        "FILTER": str(job.extra.options["FILTER"]).lower(),
        "GAIN": str(job.extra.options["GAIN"]),
        "mode": job.extra.options["mode"],
    }
    assert "stderr diagnostic" in job.log
    assert os.environ["WRAPPER_MODE"] == "server default"
    assert source.read_bytes() == b"original" and not output.parent.exists()


@pytest.mark.asyncio
async def test_custom_discovery(toolbox: Toolbox, definition: SavedDefinition, tmp_path: Path) -> None:
    missing = await toolbox.definitions.create(
        Definition(name="Missing", output_extension=".json", command=[str(tmp_path / "no executable")])
    )
    items = {item["id"]: item for item in await toolbox.tools()}
    assert items[REMUX_ID]["supports_overwrite"] is True
    assert items[definition.id]["available"] is True and items[definition.id]["supports_overwrite"] is False
    assert items[missing.id]["available"] is False and items[missing.id]["reason"]
    assert "WRAPPER_MODE" not in json.dumps(items) and sys.executable not in json.dumps(items)
    fields = items[definition.id]["options_schema"]["properties"]
    assert fields["LEVEL"] == {"type": "integer", "title": "Level", "default": 5, "minimum": 0, "maximum": 12}
    assert fields["FILTER"]["type"] == "boolean"
    assert fields["GAIN"]["type"] == "number"
    assert fields["mode"]["enum"] == ["fast", "high quality"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX executable script")
@pytest.mark.asyncio
async def test_relative_executable(toolbox: Toolbox, definition: SavedDefinition, tmp_path: Path) -> None:
    script = tmp_path / "configured wrapper"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o700)
    spec = Definition(
        name=definition.name, command=["./configured wrapper"], output_extension=definition.output_extension
    )
    assert await toolbox.definitions.replace(definition.id, spec)
    assert next(item for item in await toolbox.tools() if item["id"] == definition.id)["available"]


@pytest.mark.asyncio
async def test_shipped_definition_seed(
    toolbox: Toolbox, definition: SavedDefinition, monkeypatch: pytest.MonkeyPatch
) -> None:
    shipped = ShippedDefinition(default_key="shipped", **definition.model_dump(exclude={"id", "default"}))
    defaults = repository.DEFAULT_TOOLS
    monkeypatch.setattr(repository, "DEFAULT_TOOLS", (*defaults, shipped))
    await toolbox.definitions.seed()
    seeded = next(item for item in await toolbox.definitions.all() if item.default_key == shipped.default_key)
    assert seeded.id != definition.id and seeded.id in {item["id"] for item in await toolbox.tools()}

    updated = shipped.model_copy(update={"name": "Updated"})
    monkeypatch.setattr(repository, "DEFAULT_TOOLS", (*defaults, updated))
    await toolbox.definitions.seed()
    saved = await toolbox.definitions.get(seeded.id)
    assert saved and saved.default and saved.name == updated.name
    saved = await toolbox.definitions.get(definition.id)
    assert saved and not saved.default and saved.name == definition.name


@pytest.mark.asyncio
async def test_queued_definition(toolbox: Toolbox, source: Path, monkeypatch: pytest.MonkeyPatch, terminal) -> None:
    definition = await toolbox.definitions.create(
        Definition(name="Convert", output_extension=".txt", command=[sys.executable, "original"])
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(_ctx: Context) -> Result:
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return Result()

    async def run(_ctx: Context, _binary: str, args: list[str], *, env: dict[str, str], cwd: Path) -> None:
        output = Path(env["TB_OUT"])
        assert output.parent == cwd
        output.write_text(args[0], encoding="utf-8")

    patch_tool(monkeypatch, execute=hold)
    monkeypatch.setattr(Context, "run", run)
    await toolbox.submit(Submission(tool=REMUX_ID, file=source.name))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        accepted = await toolbox.submit(Submission(tool=definition.id, file=source.name))
        assert await toolbox.definitions.delete(definition.id)
    finally:
        release.set()

    job = await terminal(accepted.id)
    assert job.status == "succeeded" and job.result
    assert (source.parent / job.result.outputs[0]).read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {"LEVEL": 13},
        {"LEVEL": "8"},
        {"GAIN": True},
        {"mode": "unconfigured"},
        {"WRAPPER_MODE": "override"},
    ],
)
async def test_custom_rejection(
    toolbox: Toolbox, source: Path, definition: SavedDefinition, monkeypatch: pytest.MonkeyPatch, options: dict
) -> None:
    request = make_mocked_request("POST", "/api/toolbox/jobs")

    async def body() -> dict:
        return {"tool": definition.id, "file": source.name, "extra": {"options": options}}

    monkeypatch.setattr(request, "json", body)
    response = await router.jobs_submit(request, toolbox)
    assert response.status == 400 and response.text
    assert json.loads(response.text)["code"] == "VALIDATION_FAILED"
    assert not toolbox.pending


@pytest.mark.asyncio
@pytest.mark.parametrize("collision", [False, True])
async def test_custom_failure(
    toolbox: Toolbox,
    source: Path,
    definition: SavedDefinition,
    monkeypatch: pytest.MonkeyPatch,
    terminal,
    collision: bool,
) -> None:
    target = source.with_name(f"video.tool-{definition.id}.json")
    if collision:
        target.write_bytes(b"keep")

    async def run(_ctx: Context, _binary: str, _args: list[str], *, env: dict[str, str], cwd: Path) -> None:
        if collision:
            output = Path(env["TB_OUT"])
            assert output.parent == cwd
            output.write_bytes(b"result")

    monkeypatch.setattr(Context, "run", run)
    accepted = await toolbox.submit(Submission(tool=definition.id, file=source.name))
    job = await terminal(accepted.id)
    assert job.status == "failed" and job.result is None
    assert not list(source.parent.glob("*.part"))
    assert not list(Path(toolbox.config.temp_path).iterdir())
    assert source.read_bytes() == b"original"
    if collision:
        assert target.read_bytes() == b"keep" and job.error == "The output name already exists."
    else:
        assert not target.exists() and job.error_code == "FILE_FAILED"
