import argparse

from app.features.cli import operations


def test_run_routes() -> None:
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return {}

    operations.run(argparse.Namespace(command="system", system_command="check_updates"), request)
    operations.run(argparse.Namespace(command="account", account_command="sessions", sessions_command="list"), request)
    assert calls == [
        (("POST", "/api/system/check-updates"), {"params": None, "body": {}}),
        (("GET", "/api/auth/sessions"), {"params": None, "body": None}),
    ]


def test_status_aliases() -> None:
    calls = []
    request = lambda *args, **kwargs: calls.append((args, kwargs))
    operations.run(argparse.Namespace(command="system", system_command=None), request)
    operations.run(argparse.Namespace(command="stats", stats_command=None), request)
    assert [call[0][1] for call in calls] == ["/api/system/configuration", "/api/stats/latest"]


def test_bare_group_defaults() -> None:
    parser = argparse.ArgumentParser()
    operations.register(parser.add_subparsers(dest="command"))
    calls = []
    request = lambda *args, **kwargs: calls.append((args, kwargs))
    for command in ("logs", "account"):
        operations.run(parser.parse_args([command]), request)
    assert [call[0][1] for call in calls] == ["/api/logs/", "/api/auth/me"]
