from __future__ import annotations

import base64
import io
import json
import logging
import subprocess
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from yt_dlp import YoutubeDL
from yt_dlp.downloader.external import FFmpegFD
from yt_dlp.networking import Response
from yt_dlp.postprocessor.ffmpeg import FFmpegMergerPP
from yt_dlp.utils import DownloadError

from app.features.downloads.runtime.hooks import NestedLogger
from app.features.media import config as media_config
from app.features.media.handlers import widevine
from app.features.ytdlp.ytdlp import YTDLP
from app.features.ytdlp.ytdlp_opts import ARGSMerger


KID = "00112233445566778899aabbccddeeff"
KEY = "ffeeddccbbaa99887766554433221100"
PSSH = base64.b64encode(b"video initialization").decode()
MPD = f"""<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" xmlns:cenc="urn:mpeg:cenc:2013">
  <Period><AdaptationSet>
    <ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed">
      <cenc:pssh>{PSSH}</cenc:pssh>
    </ContentProtection>
  </AdaptationSet></Period>
</MPD>""".encode()
HLS = f"""#EXTM3U
#EXT-X-TARGETDURATION:1
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-KEY:METHOD=SAMPLE-AES-CTR,URI="data:text/plain;base64,{PSSH}",KEYFORMAT="{widevine.WIDEVINE_SYSTEM_ID}"
#EXT-X-MAP:URI="init.mp4"
#EXTINF:1,
segment.m4s
#EXT-X-ENDLIST
""".encode()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    executable = tmp_path / "mp4decrypt"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "source, target = map(pathlib.Path, sys.argv[-2:])\n"
        "data = source.read_bytes()\n"
        "if data == b'fail':\n"
        "    target.write_bytes(b'partial')\n"
        "    sys.stderr.write(' '.join(sys.argv))\n"
        "    sys.exit(1)\n"
        "target.write_bytes(b'' if data == b'empty' else b'clear:' + data)\n"
    )
    executable.chmod(0o700)
    (tmp_path / "secret").write_text("serve-secret\n")
    config = tmp_path / "widevine.toml"
    settings = {
        "api_url": "https://cdm.invalid/api",
        "api_key": "file:secret",
        "device": "test-device",
        "license_url": "https://license.invalid/license",
        "mp4decrypt": str(executable),
    }
    _write_config(config, settings)
    params = {
        "extractor_args": {"media": {"type": ["widevine"], "config": [str(config)]}},
        "outtmpl": str(tmp_path / "result.%(ext)s"),
        "quiet": True,
        "noprogress": True,
        "cachedir": False,
        "socket_timeout": 30,
    }
    monkeypatch.setattr(
        "app.features.media.config.Config.get_instance",
        lambda: Mock(filename_trim=0, config_path=str(tmp_path)),
    )
    return config, settings, params


def _toml_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return str(value)


def _write_config(path, settings):
    lines = ["[widevine]"]
    nested = {}
    for key, value in settings.items():
        if isinstance(value, dict):
            nested[key] = value
        else:
            lines.append(f"{key} = {_toml_value(value)}")
    for key, values in nested.items():
        lines.append(f"\n[widevine.{key}]")
        lines.extend(f"{name} = {_toml_value(value)}" for name, value in values.items())
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture
def exchange(monkeypatch):
    calls = []
    media = []
    state = {
        "failure": None,
        "keys": [{"key_id": KID, "key": KEY}],
        "manifest": MPD,
        "playlist": HLS,
        "init": b"init-",
        "master": b"#EXTM3U\n",
        "segment": b"encrypted",
        "redirect": None,
    }

    def serve(request):
        endpoint = request.url.path.split("/test-device/", 1)[1]
        body = json.loads(request.content) if request.content else None
        calls.append((endpoint, body))
        assert request.headers["X-Secret-Key"] == "serve-secret"
        assert "Authorization" not in request.headers
        if state["failure"] == endpoint:
            return httpx.Response(500, json={"status": 500, "message": "serve-secret " + KEY})
        data = {}
        if endpoint == "open":
            data = {"session_id": "session"}
        elif endpoint.startswith("get_license_challenge/"):
            data = {"challenge_b64": base64.b64encode(b"challenge").decode()}
        elif endpoint == "get_keys/CONTENT":
            data = {"keys": state["keys"]}
        return httpx.Response(200, json={"status": 200, "data": data})

    client = httpx.Client
    transport = httpx.MockTransport(serve)

    def create_client(*args, **kwargs):
        kwargs["transport"] = transport
        return client(*args, **kwargs)

    monkeypatch.setattr("app.features.media.handlers.widevine.httpx.Client", create_client)

    def urlopen(self, request):
        media.append(request)
        assert request.extensions.get("timeout", self.params.get("socket_timeout", 0)) > 0
        assert "X-Secret-Key" not in request.headers
        resource = {
            "https://media.invalid/video.m3u8": "playlist",
            "https://media.invalid/audio.m3u8": "playlist",
            "https://media.invalid/master.m3u8": "master",
            "https://media.invalid/init.mp4": "init",
            "https://media.invalid/segment.m4s": "segment",
        }.get(request.url)
        if resource:
            payload = state[resource]
            assert isinstance(payload, bytes)
            redirect = state["redirect"] if resource == "playlist" else None
            assert redirect is None or isinstance(redirect, str)
            headers = {}
            status = 200
            if byte_range := request.headers.get("Range"):
                start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
                headers["Content-Range"] = f"bytes {start}-{end}/{len(payload)}"
                payload = payload[start : end + 1]
                status = 206
            headers["Content-Length"] = str(len(payload))
            return Response(io.BytesIO(payload), url=redirect or request.url, headers=headers, status=status)
        if request.url == "https://media.invalid/manifest.mpd":
            assert request.data is None
            manifest = state["manifest"]
            assert isinstance(manifest, bytes)
            return io.BytesIO(manifest)
        assert request.url == "https://license.invalid/license"
        assert request.data in (b"challenge", base64.b64decode("CAQ="))
        return io.BytesIO(b"license")

    monkeypatch.setattr(YTDLP, "urlopen", urlopen)
    return calls, media, state


def _format(kind="video", **overrides):
    return {
        "format_id": kind,
        "url": f"https://media.invalid/{kind}.mp4",
        "manifest_url": "https://media.invalid/manifest.mpd",
        "ext": "mp4" if kind == "video" else "m4a",
        "protocol": "http_dash_segments",
        "vcodec": "h264" if kind == "video" else "none",
        "acodec": "none" if kind == "video" else "aac",
        "has_drm": True,
        "http_headers": {"Authorization": "media-token"},
        "fragments": [{"url": f"https://media.invalid/{kind}-1.m4s"}],
        **overrides,
    }


def _hls_format(kind="video", **overrides):
    return _format(
        kind,
        **{"protocol": "m3u8_native", "url": f"https://media.invalid/{kind}.m3u8", "manifest_url": None, **overrides},
    )


def _download(monkeypatch, payload=b"encrypted"):
    paths = []

    def download(self, name, info, subtitle=False, test=False):
        path = Path(name)
        path.write_bytes(payload)
        paths.append(path)
        return True, True

    monkeypatch.setattr(YoutubeDL, "dl", download)
    return paths


def _info(formats):
    return {"id": "item", "title": "item", "extractor_key": "Generic", "formats": formats}


def _handler(ydl: YTDLP) -> widevine.Widevine:
    handler = ydl._media.handler
    assert isinstance(handler, widevine.Widevine)
    return handler


def _load(options):
    settings, path = media_config.load("widevine", options)
    return widevine.validate_config(settings, options, path)


@pytest.mark.parametrize("protocol", ["http_dash_segments", "m3u8_native", "m3u8"])
def test_decrypt_before_merge(setup, exchange, monkeypatch, protocol):
    _, _, params = setup
    calls, media, _ = exchange
    paths = _download(monkeypatch)
    merged = []

    def merge(self, info):
        inputs = info["__files_to_merge"]
        contents = [Path(path).read_bytes() for path in inputs]
        assert contents == [b"clear:encrypted", b"clear:encrypted"]
        merged.extend(contents)
        Path(info["filepath"]).write_bytes(b"merged")
        return inputs, info

    monkeypatch.setattr(FFmpegMergerPP, "available", property(lambda self: True))
    monkeypatch.setattr(FFmpegMergerPP, "run", merge)
    params["format"] = "video+audio"
    fmt = _format if protocol == "http_dash_segments" else _hls_format
    with YTDLP(params, auto_init=False) as ydl:
        result = ydl.process_ie_result(_info([fmt(protocol=protocol), fmt("audio", protocol=protocol)]), download=True)
        assert ydl.params["allow_unplayable_formats"] is True
        assert "hls_prefer_native" not in ydl.params
        assert _handler(ydl).playlists == {}

    assert len(paths) == 2
    assert len(merged) == 2
    assert (paths[0].parent / "result.mp4").read_bytes() == b"merged"
    assert [endpoint for endpoint, _ in calls] == [
        "open",
        "get_license_challenge/STREAMING",
        "parse_license",
        "get_keys/CONTENT",
        "close/session",
    ]
    assert len(media) == (2 if protocol == "http_dash_segments" else 3)
    assert KEY not in json.dumps(YTDLP.sanitize_info(result))
    assert "serve-secret" not in json.dumps(YTDLP.sanitize_info(result))


@pytest.mark.parametrize("outcome", ["success", "license", "decrypt"])
def test_progress_logs(setup, exchange, monkeypatch, outcome):
    _, _, params = setup
    _, _, state = exchange
    logger = Mock()
    params["logger"] = NestedLogger(logger)
    state["failure"] = "parse_license" if outcome == "license" else None
    _download(monkeypatch, b"fail" if outcome == "decrypt" else b"encrypted")

    with YTDLP(params, auto_init=False) as ydl:
        if outcome == "success":
            ydl.process_ie_result(_info([_format()]), download=True)
        else:
            with pytest.raises(DownloadError):
                ydl.process_ie_result(_info([_format()]), download=True)

    entries = [call.kwargs for call in logger.log.call_args_list if call.kwargs["msg"].startswith("[widevine]")]
    messages = [entry["msg"] for entry in entries]
    expected = ["[widevine] Acquiring license"]
    if outcome != "license":
        expected.extend(
            ["[widevine] License acquired; decryption keys ready", "[widevine] Decrypting downloaded track"]
        )
    if outcome == "success":
        expected.append("[widevine] Track decrypted")
    assert messages == expected
    assert all(entry["level"] == logging.INFO for entry in entries)
    assert all(value not in "\n".join(messages) for value in (KEY, KID, "serve-secret", PSSH, "https://"))


def test_privacy_exchange(setup, exchange, monkeypatch):
    config, settings, params = setup
    calls, media, _ = exchange
    settings["privacy"] = True
    settings["license_headers"] = {"Authorization": "license-token"}
    _write_config(config, settings)
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format()]), download=True)

    assert [endpoint for endpoint, _ in calls] == [
        "open",
        "set_service_certificate",
        "get_license_challenge/STREAMING",
        "parse_license",
        "get_keys/CONTENT",
        "close/session",
    ]
    license_requests = [request for request in media if request.data is not None]
    assert len(license_requests) == 2
    assert all(request.headers["Authorization"] == "license-token" for request in license_requests)
    assert calls[2][1]["privacy_mode"] is True


@pytest.mark.parametrize("failure", ["parse_license", "get_keys/CONTENT"])
def test_close_on_failure(setup, exchange, monkeypatch, failure):
    _, _, params = setup
    calls, _, state = exchange
    state["failure"] = failure
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError) as error:
            ydl.process_ie_result(_info([_format()]), download=True)
        assert ydl.params["allow_unplayable_formats"] is True

    assert calls[-1][0] == "close/session"
    assert paths == []
    assert KEY not in str(error.value)
    assert "serve-secret" not in str(error.value)


@pytest.mark.parametrize("payload", [b"fail", b"empty"])
def test_preserve_failed_input(setup, exchange, monkeypatch, payload):
    _, _, params = setup
    paths = _download(monkeypatch, payload)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError) as error:
            ydl.process_ie_result(_info([_format()]), download=True)

    assert len(paths) == 1
    assert paths[0].read_bytes() == payload
    assert KEY not in str(error.value)
    assert KID not in str(error.value)
    assert set(paths[0].parent.iterdir()) == {
        paths[0],
        setup[0],
        paths[0].parent / "secret",
        paths[0].parent / "mp4decrypt",
    }


@pytest.mark.parametrize("mode", ["clear", "simulate", "skip"])
@pytest.mark.parametrize("protocol", ["http_dash_segments", "m3u8_native"])
def test_skip_key_exchange(setup, exchange, monkeypatch, mode, protocol):
    _, _, params = setup
    calls, media, _ = exchange
    fmt = _format(protocol=protocol, has_drm=mode != "clear")
    if mode == "simulate":
        params["simulate"] = True
    if mode == "skip":
        params["skip_download"] = True
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([fmt]), download=True)

    assert calls == []
    assert media == []
    assert len(paths) == (1 if mode == "clear" else 0)


def test_multiple_initialization(setup, exchange, monkeypatch):
    _, _, params = setup
    calls, _, state = exchange
    audio_pssh = base64.b64encode(b"audio initialization").decode()
    state["manifest"] = MPD.replace(
        f"<cenc:pssh>{PSSH}</cenc:pssh>".encode(),
        f"<cenc:pssh>{PSSH}</cenc:pssh><cenc:pssh>{audio_pssh}</cenc:pssh>".encode(),
    )
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format()]), download=True)

    challenges = [body for endpoint, body in calls if endpoint.startswith("get_license_challenge/")]
    assert [body["init_data"] for body in challenges] == [PSSH, audio_pssh]
    assert sum(endpoint == "close/session" for endpoint, _ in calls) == 2


def test_keys_not_reused(setup, exchange, monkeypatch):
    _, _, params = setup
    calls, _, _ = exchange
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_hls_format()]), download=True)
        second = _info([_format()])
        second["id"] = "second"
        params["outtmpl"] = str(setup[0].parent / "second.%(ext)s")
        ydl.params["outtmpl"]["default"] = params["outtmpl"]
        ydl.process_ie_result(second, download=True)

    assert sum(endpoint == "open" for endpoint, _ in calls) == 2


@pytest.mark.parametrize("protocol", ["https", "http_dash_segments_generator"])
def test_reject_unsupported_stream(setup, exchange, monkeypatch, protocol):
    _, _, params = setup
    calls, _, _ = exchange
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError):
            ydl.process_ie_result(_info([_format(protocol=protocol)]), download=True)

    assert paths == []
    assert calls == []


@pytest.mark.parametrize("method", [b"SAMPLE-AES-CTR", b"SAMPLE-AES"])
@pytest.mark.parametrize("ranged", [False, True])
def test_hls_native(setup, exchange, monkeypatch, method, ranged):
    _, _, params = setup
    calls, media, state = exchange
    params["fixup"] = "never"
    state["playlist"] = HLS.replace(b"SAMPLE-AES-CTR", method)
    if ranged:
        state["playlist"] = state["playlist"].replace(
            b"#EXTINF:1,\nsegment.m4s",
            b"#EXTINF:0.5,\n#EXT-X-BYTERANGE:4@0\nsegment.m4s\n#EXTINF:0.5,\n#EXT-X-BYTERANGE:5\nsegment.m4s",
        )

    def external(*args, **kwargs):
        pytest.fail("Protected HLS must not delegate to ffmpeg")

    monkeypatch.setattr(FFmpegFD, "real_download", external)
    with YTDLP(params, auto_init=False) as ydl:
        result = ydl.process_ie_result(_info([_hls_format()]), download=True)

    assert (setup[0].parent / "result.mp4").read_bytes() == b"clear:init-encrypted"
    assert sum(endpoint == "open" for endpoint, _ in calls) == 1
    assert [request.url for request in media if request.url.startswith("https://media.invalid/")] == [
        "https://media.invalid/video.m3u8",
        "https://media.invalid/init.mp4",
        "https://media.invalid/segment.m4s",
    ] + (["https://media.invalid/segment.m4s"] if ranged else [])
    assert "hls_media_playlist_data" not in json.dumps(YTDLP.sanitize_info(result))


@pytest.mark.parametrize(
    "playlist",
    [
        HLS.replace(b"#EXT-X-ENDLIST", b""),
        HLS.replace(b'#EXT-X-MAP:URI="init.mp4"\n', b""),
        HLS.replace(b"SAMPLE-AES-CTR", b"AES-128"),
        HLS.replace(widevine.WIDEVINE_SYSTEM_ID.encode(), b"com.apple.streamingkeydelivery"),
        HLS.replace(b"#EXT-X-ENDLIST", b'#EXT-X-MAP:URI="second.mp4"\n#EXT-X-ENDLIST'),
        HLS.replace(b"#EXTINF:1,", b"#EXT-X-DISCONTINUITY\n#EXTINF:1,"),
        HLS.replace(b"#EXTINF:1,", b"#EXT-X-GAP\n#EXTINF:1,"),
        HLS.replace(b"#EXT-X-ENDLIST", HLS.splitlines()[3] + b',KEYID="different"\n#EXT-X-ENDLIST'),
        HLS.replace(b'URI="init.mp4"', b'URI="init.mp4",BYTERANGE="0@0"'),
        HLS.replace(b'URI="init.mp4"', b'URI="init.mp4",BYTERANGE="invalid"'),
        HLS.replace(b'URI="init.mp4"', b'URI="file:///secret"'),
        HLS.replace(b"segment.m4s", b"file:///secret"),
    ],
)
def test_hls_rejects_playlist(setup, exchange, monkeypatch, playlist):
    _, _, params = setup
    calls, _, state = exchange
    state["playlist"] = playlist
    params["extractor_args"]["media"]["pssh"] = [PSSH]
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError):
            ydl.process_ie_result(_info([_hls_format()]), download=True)

    assert calls == []
    assert paths == []


def test_hls_session_key(setup, exchange, monkeypatch):
    _, _, params = setup
    calls, _, state = exchange
    key = HLS.splitlines()[3]
    state["playlist"] = HLS.replace(key + b"\n", b"")
    state["master"] = b"#EXTM3U\n" + key.replace(b"EXT-X-KEY", b"EXT-X-SESSION-KEY") + b"\n"
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_hls_format(manifest_url="https://media.invalid/master.m3u8")]), download=True)

    assert calls[1][1]["init_data"] == PSSH


def _box(kind, payload):
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


@pytest.mark.parametrize("ranged", [False, True])
@pytest.mark.parametrize("location", ["top", "moov", "extended", "zero"])
def test_hls_init_pssh(setup, exchange, monkeypatch, ranged, location):
    _, _, params = setup
    calls, media, state = exchange
    box = _box(b"pssh", b"\x00" * 4 + bytes.fromhex(widevine.WIDEVINE_SYSTEM_ID[9:].replace("-", "")) + b"\x00" * 4)
    if location == "top":
        state["init"] = box
    elif location == "extended":
        state["init"] = b"\x00\x00\x00\x01moov" + (len(box) + 16).to_bytes(8, "big") + box
    elif location == "zero":
        state["init"] = b"\x00\x00\x00\x00moov" + box
    else:
        state["init"] = _box(b"moov", box)
    length = len(state["init"])
    state["playlist"] = HLS.replace(f"data:text/plain;base64,{PSSH}".encode(), b"https://license.invalid/license")
    if ranged:
        state["playlist"] = state["playlist"].replace(
            b'URI="init.mp4"', f'URI="init.mp4",BYTERANGE="{length}@17"'.encode()
        )
        state["init"] = b"\x00" * 17 + state["init"]
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_hls_format()]), download=True)

    assert calls[1][1]["init_data"] == base64.b64encode(box).decode()
    request = next(request for request in media if request.url.endswith("init.mp4"))
    assert request.headers.get("Range") == (f"bytes=17-{16 + length}" if ranged else None)


def test_hls_redirect(setup, exchange, monkeypatch):
    _, _, params = setup
    _, _, state = exchange
    state["redirect"] = "https://media.invalid/redirect/video.m3u8"

    def download(self, name, info, subtitle=False, test=False):
        assert info["url"] == state["redirect"]
        assert info["hls_media_playlist_data"] == HLS.decode()
        assert self.params["allow_unplayable_formats"] is True
        assert self.params["hls_prefer_native"] is True
        Path(name).write_bytes(b"encrypted")
        return True, True

    monkeypatch.setattr(YoutubeDL, "dl", download)
    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_hls_format()]), download=True)

    assert (setup[0].parent / "result.mp4").read_bytes() == b"clear:encrypted"


@pytest.mark.parametrize("keys", [[], [{"key_id": "invalid", "key": KEY}], [{"key_id": KID, "key": "invalid"}]])
def test_reject_invalid_keys(setup, exchange, monkeypatch, keys):
    _, _, params = setup
    calls, _, state = exchange
    state["keys"] = keys
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError):
            ydl.process_ie_result(_info([_format()]), download=True)

    assert calls[-1][0] == "close/session"
    assert paths == []


def test_retry_encrypted_input(setup, exchange, monkeypatch):
    _, _, params = setup
    existing = setup[0].parent / "result.mp4"
    existing.write_bytes(b"encrypted")

    def download(self, name, info, subtitle=False, test=False):
        assert Path(name) == existing
        return True, False

    monkeypatch.setattr(YoutubeDL, "dl", download)
    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format()]), download=True)

    assert existing.read_bytes() == b"clear:encrypted"


@pytest.mark.parametrize("interrupted", [False, True])
@pytest.mark.parametrize("protocol", ["http_dash_segments", "m3u8_native"])
def test_stop_processor(setup, exchange, monkeypatch, interrupted, protocol):
    _, _, params = setup
    paths = _download(monkeypatch)
    process = Mock(returncode=-9, stderr=io.BytesIO())
    process.poll.return_value = None
    process.communicate.side_effect = KeyboardInterrupt if interrupted else subprocess.TimeoutExpired(KEY, 60)
    monkeypatch.setattr("app.features.media.handlers.widevine.subprocess.Popen", lambda *args, **kwargs: process)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(KeyboardInterrupt if interrupted else DownloadError) as error:
            fmt = _format if protocol == "http_dash_segments" else _hls_format
            ydl.process_ie_result(_info([fmt()]), download=True)
        assert ydl.params["allow_unplayable_formats"] is True
        assert _handler(ydl).keys is None
        assert _handler(ydl).ids == set()
        assert _handler(ydl).playlists == {}
        assert "hls_prefer_native" not in ydl.params

    process.kill.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)
    assert process.stderr.closed
    assert paths[0].read_bytes() == b"encrypted"
    assert not list(paths[0].parent.glob(".widevine-*"))
    assert KEY not in str(error.value)


def test_explicit_initialization(setup, exchange, monkeypatch):
    _, _, params = setup
    calls, media, _ = exchange
    params["extractor_args"]["media"]["pssh"] = [PSSH]
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format(manifest_url=None)]), download=True)

    assert len(media) == 1
    assert calls[1][1]["init_data"] == PSSH


def test_advertised_license(setup, exchange, monkeypatch):
    config, settings, params = setup
    _, media, state = exchange
    del settings["license_url"]
    _write_config(config, settings)
    state["manifest"] = MPD.replace(
        b"</ContentProtection>",
        b'<Laurl xmlns="urn:dashif:org:cp">https://license.invalid/license</Laurl></ContentProtection>',
    )
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format()]), download=True)

    assert media[-1].url == "https://license.invalid/license"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("api_url", "file:///secret"),
        ("api_key", "file:"),
        ("device", " "),
        ("license_url", "ftp://license.invalid"),
        ("privacy", "false"),
        ("license_type", ["STREAMING"]),
        ("license_headers", {"Authorization": 123}),
        ("mp4decrypt", " "),
    ],
)
def test_invalid_configuration(setup, key, value):
    config, settings, params = setup
    settings[key] = value
    _write_config(config, settings)

    with pytest.raises(ValueError) as error:
        YTDLP(params, auto_init=False)

    assert "serve-secret" not in str(error.value)


@pytest.mark.parametrize("protocol", ["http_dash_segments", "m3u8_native"])
def test_reject_external_merge(setup, exchange, monkeypatch, protocol):
    _, _, params = setup
    calls, media, _ = exchange
    params["external_downloader"] = "ffmpeg"
    params["format"] = "video+audio"
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError):
            ydl.process_ie_result(
                _info([_format(protocol=protocol), _format("audio", protocol=protocol)]), download=True
            )

    assert paths == []
    assert calls == []
    assert media == []


def test_reject_other_container(setup, exchange, monkeypatch):
    _, _, params = setup
    calls, media, _ = exchange
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        with pytest.raises(DownloadError):
            ydl.process_ie_result(_info([_format(ext="webm", vcodec="vp9")]), download=True)

    assert paths == []
    assert calls == []
    assert media == []


def test_cli_configuration(setup):
    config, _, params = setup
    options = (
        ARGSMerger()
        .add(f'--extractor-args "media:type=widevine;config={config};license_url=https://license.invalid/license"')
        .as_ytdlp()
    )
    params["extractor_args"] = options["extractor_args"]

    with YTDLP(params, auto_init=False) as ydl:
        result = ydl.process_ie_result(_info([_format()]), download=False)

    assert result["formats"][0]["has_drm"] is True
    assert result["formats"][0]["format_id"] == "video"


def test_license_url_override(setup, exchange, monkeypatch):
    config, settings, params = setup
    _, media, _ = exchange
    settings["license_url"] = "https://unused.invalid/license"
    _write_config(config, settings)
    options = (
        ARGSMerger()
        .add(f'--extractor-args "media:type=widevine;config={config};license_url=https://license.invalid/license"')
        .as_ytdlp()
    )
    params["extractor_args"] = options["extractor_args"]
    _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format()]), download=True)

    assert media[-1].url == "https://license.invalid/license"


def test_invalid_url_override(setup):
    _, _, params = setup
    params["extractor_args"]["media"]["license_url"] = ["file:///secret"]

    with pytest.raises(ValueError):
        YTDLP(params, auto_init=False)


@pytest.mark.parametrize("relative", [False, True])
def test_config_override(setup, relative):
    config, settings, params = setup
    folder = config.parent / "presets"
    folder.mkdir()
    (folder / "secret").write_text("preset-secret\n")
    selected = folder / "widevine.toml"
    _write_config(selected, {**settings, "device": "preset-device", "license_headers": {"X-Preset": "yes"}})
    _write_config(config, {**settings, "privacy": True})
    filename = selected.relative_to(config.parent) if relative else selected
    params["extractor_args"] = (
        ARGSMerger().add(f'--extractor-args "media:type=widevine;config={filename}"').as_ytdlp()["extractor_args"]
    )

    with YTDLP(params, auto_init=False) as ydl:
        loaded = _handler(ydl).config
        assert loaded is not None
        assert loaded["device"] == "preset-device"
        assert loaded["api_key"] == "preset-secret"
        assert loaded["license_headers"] == {"X-Preset": "yes"}
        assert "privacy" not in loaded
        assert ydl.params["allow_unplayable_formats"] is True

    with YTDLP(
        {"quiet": True, "extractor_args": {"media": {"type": ["widevine"], "config": [str(config)]}}}, auto_init=False
    ) as ydl:
        loaded = _handler(ydl).config
        assert loaded["device"] == "test-device"
        assert loaded["api_key"] == "serve-secret"
        assert loaded["privacy"] is True


def test_preset_download(setup, exchange, monkeypatch):
    config, settings, params = setup
    calls, media, _ = exchange
    selected = config.parent / "preset.toml"
    _write_config(
        selected,
        {**settings, "license_url": "https://unused.invalid", "license_headers": {"Authorization": "preset-token"}},
    )
    config.write_text('[auth]\nexternal_user = "admin"\n')
    params["extractor_args"] = (
        ARGSMerger()
        .add(
            f'--extractor-args "media:type=widevine;config={selected};license_url=https://license.invalid/license;pssh={PSSH}"'
        )
        .as_ytdlp()["extractor_args"]
    )
    paths = _download(monkeypatch)

    with YTDLP(params, auto_init=False) as ydl:
        ydl.process_ie_result(_info([_format(manifest_url=None)]), download=True)

    assert paths[0].read_bytes() == b"clear:encrypted"
    assert calls[1][1]["init_data"] == PSSH
    assert len(media) == 1
    assert media[0].url == "https://license.invalid/license"
    assert media[0].headers["Authorization"] == "preset-token"


@pytest.mark.parametrize("kind", ["missing", "malformed", "unconfigured", "incomplete", "directory"])
def test_invalid_config_override(setup, kind):
    config, _, _ = setup
    selected = config.parent / "selected.toml"
    if kind == "directory":
        selected.mkdir()
    elif kind != "missing":
        selected.write_text(
            {"malformed": "[widevine\n", "unconfigured": "[auth]\n", "incomplete": '[widevine]\ndevice="device"\n'}[
                kind
            ]
        )

    with pytest.raises(ValueError) as error:
        _load({"config": str(selected)})

    assert "serve-secret" not in str(error.value)
    assert _load({"config": str(config)}) is not None


@pytest.mark.parametrize("options", [{"license_url": "https://license.invalid/license"}, {"pssh": PSSH}])
def test_requires_config(options):
    with pytest.raises(ValueError, match="config"):
        _load(options)


def test_malformed_config(tmp_path, monkeypatch):
    selected = tmp_path / "widevine.toml"
    selected.write_text("[widevine\n")
    monkeypatch.setattr("app.features.media.config.Config.get_instance", lambda: Mock(config_path=str(tmp_path)))

    with pytest.raises(ValueError):
        _load({"config": str(selected)})


def test_invalid_table(tmp_path, monkeypatch):
    selected = tmp_path / "widevine.toml"
    selected.write_text('widevine = "disabled"\n')
    monkeypatch.setattr("app.features.media.config.Config.get_instance", lambda: Mock(config_path=str(tmp_path)))

    with pytest.raises(ValueError):
        _load({"config": str(selected)})
