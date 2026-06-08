from __future__ import annotations

import os
import tempfile

from app.tests.helpers import cleanup_test_run_root, get_test_run_root, get_test_system_temp_root


def pytest_configure(config) -> None:
    temp_root = get_test_system_temp_root()
    for env_name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[env_name] = str(temp_root)

    tempfile.tempdir = None

    if getattr(config.option, "basetemp", None) is None:
        config.option.basetemp = str(get_test_run_root() / "pytest")

    os.environ["YTP_FILE_LOGGING"] = "false"


def pytest_unconfigure(config) -> None:
    del config
    os.environ.pop("YTP_FILE_LOGGING", None)
    cleanup_test_run_root()
