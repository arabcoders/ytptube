import argparse

import pytest

from app.features.cli.downloads import human, register, run


def parser():
    root = argparse.ArgumentParser()
    root.add_argument("--url")
    register(root.add_subparsers(dest="command", required=True))
    return root


def test_add_request():
    args = parser().parse_args(["downloads", "add", "https://x", "--folder", "f", "--cli=--foo"])
    calls = []
    run(args, lambda *a, **kw: calls.append((a, kw)) or {"status": "ok"})
    assert calls == [((("POST", "/api/history/")), {"body": {"url": "https://x", "folder": "f", "cli": "--foo"}})]


def test_list_request():
    args = parser().parse_args(["downloads", "list", "--type", "done", "--source-id", "4"])
    calls = []
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][0] == ("GET", "/api/history/")
    assert calls[0][1]["params"]["source_id"] == 4


def test_add_file(tmp_path):
    file = tmp_path / "batch.json"
    file.write_text('[{"url":"https://example.test/one"},{"url":"https://example.test/two"}]')
    args = parser().parse_args(["downloads", "add", "--file", str(file)])
    calls = []
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls == [
        (
            ("POST", "/api/history/"),
            {"body": [{"url": "https://example.test/one"}, {"url": "https://example.test/two"}]},
        )
    ]


def test_add_rejects_mix():
    args = parser().parse_args(["downloads", "add", "https://example.test", "--data", '{"url":"other"}'])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)


def test_delete_status():
    args = parser().parse_args(["downloads", "batch", "--delete", "--type", "done", "--status", "error"])
    calls = []
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls == [(("DELETE", "/api/history/"), {"body": {"type": "done", "remove_file": False, "status": "error"}})]


def test_add_urls():
    calls = []
    args = parser().parse_args(["downloads", "add", "https://one", "https://two"])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == [{"url": "https://one"}, {"url": "https://two"}]


def test_batch_rejects_mix():
    args = parser().parse_args(["downloads", "batch", "--retry", "one", "--status", "failed"])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)


def test_batch_delete_options():
    args = parser().parse_args(["downloads", "batch", "--retry", "--type", "queue", "one"])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)
    args = parser().parse_args(["downloads", "batch", "--start", "--remove-file", "one"])
    with pytest.raises(ValueError):
        run(args, lambda *a, **kw: None)


def test_retry_payload():
    calls = []
    args = parser().parse_args(["downloads", "batch", "--retry", "one", "two"])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == {"ids": ["one", "two"]}
    calls.clear()
    args = parser().parse_args(["downloads", "batch", "--retry", "--status", "failed"])
    run(args, lambda *a, **kw: calls.append((a, kw)))
    assert calls[0][1]["body"] == {"status": "failed"}
