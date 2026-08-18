from unittest.mock import Mock

from app import main


def test_accepts_process_arg(monkeypatch):
    start = Mock()
    monkeypatch.setattr(main, "start", start)

    main.main(["--ytp-process"])

    start.assert_called_once_with()
