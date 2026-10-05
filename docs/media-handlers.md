# Media handlers

Use the `media` extractor arguments to select a handler for a download or preset.

## Selecting a handler

```bash
--extractor-args "media:type=HANDLER;config=/config/handler.toml"
```

Replace `HANDLER` with the handler type. Both `type` and `config` are required. The TOML file must contain a table
named after the selected type. Without `media` options, downloads use the normal yt-dlp behavior.

Relative config paths start at `YTP_CONFIG_PATH`. Container paths must be accessible inside the container.
An unknown handler type or invalid configuration fails the download.

Handler-specific options also belong in the `media` namespace.

## Widevine

The Widevine handler downloads protected media you own or are authorized to download. It obtains content keys from
your own `pywidevine` instance and decrypts each track with `mp4decrypt` before merging. No `--allow-unplayable-formats`
is needed.

```bash
--extractor-args "media:type=widevine;config=/config/widevine.toml"
```

> [!IMPORTANT]
> YTPTube does not provide device credentials, cdm devices or grant access to a license server.

### Setup

Run a [pywidevine](https://github.com/devine-dl/pywidevine) instance with your device configured and allow YTPTube
to reach it. The YTPTube container includes `mp4decrypt`, but not the key service or its devices. For native
installations, install Bento4's `mp4decrypt` on `PATH`, or set its executable path in the configuration below.

Create a TOML file, such as `/config/widevine.toml`, with a `[widevine]` table:

```toml
[widevine]
api_url = "https://cdm.example.org" # pywidevine server base URL
api_key = "file:secrets/widevine-api-key"
device = "my-device" # Server device name, not a file path

# Optional overrides when stream metadata is missing:
# license_url = "https://media.example.org/license"
# pssh = "BASE64_PSSH"

# Optional settings, shown with their defaults:
privacy = false # Enable service certificate exchange with true
license_type = "STREAMING" # Also accepts OFFLINE or AUTOMATIC
mp4decrypt = "mp4decrypt" # Executable name or path
```

Put the API key in `secrets/widevine-api-key`, relative to that file, or use a literal `api_key` value.

Optional headers for the license server, not the pywidevine server:

```toml
[widevine.license_headers]
Authorization = "Bearer YOUR_PLAYBACK_TOKEN"
```

License requests also use yt-dlp's configured cookies and proxy settings.

### Download overrides

`license_url` and `pssh` override the selected file's values for that download:

```bash
--extractor-args "media:type=widevine;config=/config/widevine.toml;license_url=https://media.example.org/license;pssh=BASE64_PSSH"
```

`file:` secret paths start at the selected file's directory. Content keys stay in memory during the download;
YTPTube does not add them to metadata files or download logs.

### Limitations

- Supported downloads are on-demand DASH and fragmented MP4 HLS tracks in MP4 or M4A containers.
- HLS requires an `EXT-X-MAP` initialization segment, `SAMPLE-AES` (CBCS) or `SAMPLE-AES-CTR` (CENC), and a Widevine
  key declaration using `KEYFORMAT="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"`. Initialization data can come from
  the key's data URI, a master playlist's session key, the initialization MP4, or the `pssh` override.
- Protected HLS with MPEG-TS segments, key rotation, discontinuities, or changing initialization segments is not
  supported.
- WebM, live streams, partial downloads, stdout output, and external downloaders are not supported for protected tracks.
- The license server must accept a raw binary challenge and return a raw binary license. Site-specific JSON wrappers
  and other custom license protocols are not supported.
- Clear, simulated, and skip-download requests do not acquire content keys. If decryption fails, YTPTube does not
  replace or merge the encrypted track, and the download fails. Normal temporary-file cleanup settings still apply.
