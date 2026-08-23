from app.features.tasks.definitions.utils import archive_key


def test_keys_use_urls() -> None:
    url = "https://example.com/video?id=1"

    key = archive_key(url)

    assert key == "a:5a25a3abaa3fc28c"
    assert key != archive_key(f"{url}0")
