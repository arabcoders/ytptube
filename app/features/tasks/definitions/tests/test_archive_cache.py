import hashlib

from app.features.tasks.definitions.utils import archive_id_cache_key


def test_keys_use_urls() -> None:
    url = "https://example.com/video?id=1"

    assert archive_id_cache_key(url) == f"tasks:archive-id:{hashlib.sha256(url.encode()).hexdigest()}"
    assert archive_id_cache_key(url) == archive_id_cache_key(url)
