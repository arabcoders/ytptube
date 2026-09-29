import argparse

import pytest

from app.features.cli.resources import register, run


def parser():
    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(dest="command", required=True))
    return parser


def test_mapping():
    args = parser().parse_args(["presets", "list", "--page", "2"])
    calls = []
    result = run(args, lambda *a, **kw: calls.append((a, kw)) or {"ok": True})
    assert result == {"ok": True}
    assert calls == [(("GET", "/api/presets/"), {"params": {"page": 2, "per_page": 50}, "body": None})]


def test_list_flags():
    calls = []
    for command in (
        ["presets", "list", "--exclude-defaults"],
        ["task-definitions", "list", "--include-definition"],
    ):
        run(parser().parse_args(command), lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["params"]["exclude_defaults"] is True
    assert calls[1][1]["params"]["include"] == "definition"


def test_commands():
    calls = []
    for command in (
        ["tasks", "inspect", "--data", '{"url":"x"}'],
        ["notifications", "events"],
        ["notifications", "test"],
    ):
        run(parser().parse_args(command), lambda *a, **kw: calls.append((a, kw)))

    assert calls[0] == (("POST", "/api/tasks/inspect"), {"params": None, "body": {"url": "x"}})
    assert calls[1] == (("GET", "/api/notifications/events/"), {"params": {}, "body": None})
    assert calls[2] == (("POST", "/api/notifications/test/"), {"params": None, "body": None})


def test_inspect_url_options():
    calls = []
    args = parser().parse_args(
        ["tasks", "inspect", "https://example.com", "--preset", "fast", "--static-only", "--no-resolve-ids"]
    )
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == {
        "url": "https://example.com",
        "preset": "fast",
        "static_only": True,
        "resolve_ids": False,
    }


def test_condition_url_dispatch():
    calls = []
    args = parser().parse_args(["conditions", "test", "https://example.com", "title == 'Example'", "--preset", "fast"])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == {"url": "https://example.com", "condition": "title == 'Example'", "preset": "fast"}


def test_definition_target_dispatch():
    calls = []
    args = parser().parse_args(["task-definitions", "inspect", "12", "https://example.com"])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == {"definition_id": 12, "url": "https://example.com"}


def test_positional_body_conflict():
    args = parser().parse_args(["tasks", "inspect", "https://example.com", "--data", '{"url":"other"}'])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)


def test_definition_requires_url():
    args = parser().parse_args(["task-definitions", "inspect", "12"])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)


def test_task_mark_route():
    args = parser().parse_args(["tasks", "mark", "4"])
    calls = []
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls == [(("POST", "/api/tasks/4/mark"), {"params": None, "body": None})]


def test_update_route(tmp_path):
    body_file = tmp_path / "body.json"
    body_file.write_text('{"enabled":false}', encoding="utf-8")
    calls = []
    args = parser().parse_args(["tasks", "update", "4", "--file", str(body_file)])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls == [(("PATCH", "/api/tasks/4"), {"params": None, "body": {"enabled": False}})]


def test_bad_body_file(tmp_path):
    body_file = tmp_path / "body.json"
    body_file.write_text("not json", encoding="utf-8")
    args = parser().parse_args(["conditions", "test", "--file", str(body_file)])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)
