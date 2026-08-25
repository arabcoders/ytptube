# Environment variables

Certain configuration values can be set via environment variables, using the `-e` parameter on the docker command line, 
or the `environment:` section in `compose.yaml` file.

> [!NOTE]
>
> Most environment variables are shared between native and container deployments, but some default values differ for 
> native builds. See [Native builds](docs/native-builds.md#files-and-settings) for the native-specific defaults.

<details>
<summary>Click to expand all environment variables</summary>

| Environment Variable            | Description                                                         | Default               |
| ------------------------------- | ------------------------------------------------------------------- | --------------------- |
| TZ                              | The timezone to use for the application                             | `(not_set)`           |
| YTP_OUTPUT_TEMPLATE             | The template for the filenames of the downloaded videos             | `%(title)s.%(ext)s`   |
| YTP_DEFAULT_PRESET              | The default preset to use for the download                          | `default`             |
| YTP_INSTANCE_TITLE              | The title of the instance                                           | `(not_set)`           |
| YTP_FILE_LOGGING                | Whether to log to file                                              | `true`                |
| YTP_DOWNLOAD_PATH               | Path to where the downloads will be saved                           | `/downloads`          |
| YTP_MAX_WORKERS                 | The maximum number of workers to use for downloading                | `20`                  |
| YTP_MAX_WORKERS_PER_EXTRACTOR   | The maximum number of concurrent downloads per extractor            | `2`                   |
| YTP_MONITOR_ENABLED             | Enable app resource monitoring                                      | `false`               |
| YTP_MONITOR_INTERVAL            | Sampling interval in seconds for resource monitoring                | `30`                  |
| YTP_MONITOR_RETENTION_HOURS     | How many hours to retain raw monitor samples in the stats database  | `24`                  |
| YTP_DISABLE_AUTH                | Disable application authentication                                  | `false`               |
| YTP_AUTH_SESSION_DAYS           | Number of days before browser sessions expire (minimum `1`)         | `30`                  |
| YTP_CORS_ORIGINS                | Comma-separated exact origins, or `*` for non-cookie clients        | `*`                   |
| YTP_TRUSTED_PROXIES             | Comma-separated proxy IP addresses and/or CIDRs trusted for XFF     | `(empty)`             |
| YTP_CONSOLE_ENABLED             | Whether to enable the console                                       | `false`               |
| YTP_REMOVE_FILES                | Remove the actual file when clicking the remove button              | `false`               |
| YTP_CONFIG_PATH                 | Path to where the config files will be stored.                      | `/config`             |
| YTP_TEMP_PATH                   | Path to where tmp files are stored.                                 | `/tmp`                |
| YTP_TEMP_KEEP                   | Whether to keep the Individual video temp directory or remove it    | `false`               |
| YTP_HOST                        | Which IP address to bind to                                         | `0.0.0.0`             |
| YTP_PORT                        | Which port to bind to                                               | `8081`                |
| YTP_LOG_LEVEL                   | Log level                                                           | `info`                |
| YTP_STREAMER_VCODEC             | The video encoding codec, default to GPU and fallback to software   | `""`                  |
| YTP_STREAMER_ACODEC             | The audio codec to use for in-browser streaming                     | `aac`                 |
| YTP_VAAPI_DEVICE                | The VAAPI device to use for hardware acceleration.                  | `/dev/dri/renderD128` |
| YTP_ACCESS_LOG                  | Whether to log access to the web server                             | `true`                |
| YTP_DEBUG                       | Whether to turn on debug mode                                       | `false`               |
| YTP_DEBUGPY_PORT                | The port to use for the debugpy debugger                            | `5678`                |
| YTP_EXTRACT_INFO_TIMEOUT        | The timeout for extracting video information                        | `70`                  |
| YTP_EXTRACT_INFO_KEEP_ALIVE     | Keep extract info worker processes alive between requests           | `false`               |
| YTP_PIP_PACKAGES                | A space separated list of pip packages to install                   | `(not_set)`           |
| YTP_PIP_IGNORE_UPDATES          | Do not update the custom pip packages                               | `false`               |
| YTP_PYTHON_PATH                 | Extra python library directory                                      | `(not_set)`           |
| YTP_PICTURES_BACKENDS           | A comma separated list of picture URLs to use                       | `(default)`           |
| YTP_BROWSER_CONTROL_ENABLED     | Whether to enable the file browser actions                          | `false`               |
| YTP_YTDLP_AUTO_UPDATE           | Whether to enable the auto update for yt-dlp                        | `true`                |
| YTP_YTDLP_DEBUG                 | Whether to turn debug logging for the internal `yt-dlp` package     | `false`               |
| YTP_YTDLP_VERSION               | The version of yt-dlp to use. Defaults to latest version            | `(not_set)`           |
| YTP_BROWSER_URL                 | Remote browser endpoint for the browser extractor                   | `(not_set)`           |
| YTP_FLARESOLVERR_URL            | FlareSolverr or Trawl endpoint URL.                                 | `(not_set)`           |
| YTP_FLARESOLVERR_MAX_TIMEOUT    | Max FlareSolverr/Trawl challenge timeout in seconds                 | `120`                 |
| YTP_FLARESOLVERR_CLIENT_TIMEOUT | HTTP client timeout (seconds) when calling FlareSolverr/Trawl       | `120`                 |
| YTP_FLARESOLVERR_CACHE_TTL      | The cache TTL (in seconds) for FlareSolverr/Trawl solutions         | `600`                 |
| YTP_BASE_PATH                   | Set this if you are serving YTPTube from sub-folder                 | `/`                   |
| YTP_PREVENT_LIVE_PREMIERE       | Prevents the initial YouTube premiere stream from being downloaded  | `true`                |
| YTP_QUEUE_DISPLAY_LIMIT         | Max queued downloads returned to the UI. `0` = unlimited            | `100`                 |
| YTP_LIVE_PREMIERE_BUFFER        | buffer time in minutes to add to video duration                     | `5`                   |
| YTP_TASKS_HANDLER_TIMER         | The cron expression for the tasks handler timer                     | `15 */1 * * *`        |
| YTP_TEMP_DISABLED               | Disable temp files handling.                                        | `false`               |
| YTP_RETRY                       | Number of additional attempts for retryable download failures.      | `0`                   |
| YTP_RETRY_FRESH                 | Use a fresh download on the final retry attempt.                    | `false`               |
| YTP_SIMPLE_MODE                 | Switch default interface to Simple mode.                            | `false`               |
| YTP_STATIC_UI_PATH              | Path to custom static UI files.                                     | `(not_set)`           |
| YTP_AUTO_CLEAR_HISTORY_DAYS     | Number of days after which completed download history is cleared.   | `0`                   |
| YTP_DEFAULT_PAGINATION          | The default number of items per page for history.                   | `50`                  |
| YTP_TASK_HANDLER_RANDOM_DELAY   | The maximum random delay in seconds before starting a task handler. | `60`                  |
| YTP_IGNORE_ARCHIVED_ITEMS       | Don't report archived items in the download history.                | `false`               |
| YTP_CHECK_FOR_UPDATES           | Whether to check for application updates.                           | `true`                |
| YTP_EXTRACT_INFO_CONCURRENCY    | The number of concurrent extract info operations.                   | `4`                   |
| YTP_THUMB_CONCURRENCY           | The number of concurrent ffmpeg thumbnail generations allowed.      | `2`                   |
| YTP_THUMB_GENERATE              | Enable ffmpeg thumbnail generation when no local thumbnail exists.  | `true`                |
| YTP_THUMB_SIDECAR               | Save generated thumbnails next to media instead of temp cache.      | `false`               |

> [!NOTE]
> To raise the worker limit for a specific extractor, set an env variable using this format: `YTP_MAX_WORKERS_FOR_<EXTRACTOR_NAME>`
> The extractor name must be uppercase. You can find the extractor name in the download logs. This value cannot be 
> higher than `YTP_MAX_WORKERS`; higher values are ignored.
>
> `YTP_SIMPLE_MODE=true` only applies when the browser has no saved layout choice yet. Users can still choose a layout in 
> WebUI Settings. `/?simple=1` forces and saves Simple for that browser.
> 
> `YTP_AUTO_CLEAR_HISTORY_DAYS`  `0` days means no automatic clearing of the download history. lowest value that will 
> trigger the clearing is `1` day. This setting will **NOT** delete the downloaded files, it will only clear the 
> history from the database.
>
> `YTP_EXTRACT_INFO_KEEP_ALIVE=true` keeps yt-dlp metadata extraction worker processes alive between requests. This
> can make playlist extraction faster, but uses more idle memory. Leave it `false` to reduce idle resource usage.
</details>

# Browser extensions & bookmarklets

## Simple bookmarklet

```javascript
javascript:(() => { const url = "https://ytp.example.org"; const preset = "default"; const apiKey = "ytp_..."; const mUrl = new URL(url);mUrl.pathname="/api/history/add";mUrl.searchParams.set("url",document.location.href);mUrl.searchParams.set("preset",preset);fetch(mUrl,{method: "GET",headers:{Authorization:`Bearer ${apiKey}`}}).then(j => j.json()).then(json =>alert(json.message)).catch(err =>alert(err)); })()
```

Set `url`, `preset`, and `apiKey` for your YTPTube instance. Create the API key from the account menu.

> [!NOTE]
> The bookmarklet should be served from https page, otherwise, some browsers will block the request. for mixed content.

## Browser stores

- For Firefox via [Firefox Store](https://addons.mozilla.org/en-US/firefox/addon/ytptube-extension/)
- For Chrome/Chromium Browsers via [Chrome Store](https://chromewebstore.google.com/detail/ytptube-extension/kiepfnpeflemfokokgjiaelddchglfil)

## iOS Shortcuts

You can download [Add To YTPTube](https://www.icloud.com/shortcuts/6df61c97d97b4e539c9100999ba39dd4) shortcut and use it 
to send links to your YTPTube instance. You have to edit the shortcut and replace the following:

- `https://ytp.example.org` with your YTPTube instance.
- The shortcut currently uses Basic authentication. Replace its credential value with `username:ytp_...`: your account
  username and an API key, not your account password. Leave it empty when authentication is disabled.

This shortcut lets you select a preset from your instance. You can add presets for websites that need cookies and use
those presets to download directly from your iOS device.

### Advanced iOS Shortcut

This shortcut [YTPTube To Media](https://www.icloud.com/shortcuts/4dc579382f254635ad5785424055f173) parses the `yt-dlp`
output and attempts to download media directly to your iOS device. It doesn't always work. We provide no support for
this use case beyond the shortcut itself. The shortcut doesn't parse `http_headers`; it parses only cookies.

# Authentication

Server installations require a local account by default. Open the account menu, select **Create key**, enter a name, 
and copy the key when it appears. The key is shown once.

Send API keys in the `Authorization: Bearer ytp_...` header.

The `?apikey=ytp_...` query parameter is available for clients that cannot set headers, but URLs can appear in browser 
history and proxy logs.

Use `YTP_DISABLE_AUTH=true` only when a trusted reverse proxy controls access. `YTP_CORS_ORIGINS` accepts a
comma-separated origin allowlist. Set it to `*` for clients that send an API key without cookies.

When YTPTube is behind a reverse proxy, session details use the transport peer address by default. To record the
actual client address from `X-Forwarded-For`, set `YTP_TRUSTED_PROXIES` to the proxy's exact IP address or CIDR (for
example, `10.0.0.10,10.0.0.0/24`).

## How do I reset a forgotten password?

You need shell access to the machine running YTPTube. Replace `USERNAME` with the account username.

Assuming your YTPTube container is called `ytptube`, run:

```bash
docker exec -ti -w /app ytptube python -m app.scripts.reset_password --username USERNAME
```

For Podman, replace `docker` with `podman` in the command above.

A successful password reset invalidates the related user's sessions.

# Security recommendations

**Do not expose YTPTube to an untrusted network without authentication.**

### Without auth, anyone who can reach the API can:

- Download arbitrary content through your IP and server.
- Delete or modify your downloaded files and database.
- Run arbitrary `yt-dlp` options, including `--exec`, which executes shell commands inside the container.

The `cli options` field passes options to `yt-dlp`. Options such as `--exec` can run commands on the host or 
inside the container.

**If you expose YTPTube to untrusted networks**, do one of the following:

1. **Enable authentication**.
2. **Put it behind a reverse proxy** with its own authentication layer (see [Run behind reverse proxy](#run-behind-reverse-proxy)).
3. **Keep it on a private network** with no public exposure.

# I cant download anything

If you are receiving errors like:
- "OSError: [Errno 5] I/O error"
- "OSError: [Errno 18] Cross-device link: '/tmp/random_id/name.webm' -> '/downloads/name.webm'
- "Operation not permitted: '/downloads/name.webm'

This indicates an error with your mounts and how they interact with the container. So, the basic solution is to do the following:

<details>
<summary>Download paths Compose example</summary>

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}" # change this to your user id and group id, for example: "1000:1000"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    environment:
      - YTP_TEMP_PATH=/downloads/tmp
      - YTP_DOWNLOAD_PATH=/downloads/files
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads:rw
```

</details>

Then run the following command to create the necessary directories and start the container:

```bash
mkdir -p ./config && mkdir -p ./downloads/{tmp,files} && docker compose -f compose.yaml up -d
```

Reference: [Issue #363](https://github.com/arabcoders/ytptube/issues/363)

# I want to use link with playlist but only download the video not all the videos in the playlist?

You can do it in 3 different ways:

1. use the `--no-playlist` option in the `CLI options` field in the download form.

2. create custom field using type bool and set the field as `--no-playlist` or use the following import string

<details>
<summary>import as custom field</summary>

```text
eyJuYW1lIjoiTm8gcGxheWxpc3QiLCJkZXNjcmlwdGlvbiI6ImRvIG5vdCBwcm9jZXNzIHBsYXlsaXN0IiwiZmllbGQiOiItLW5vLXBsYXlsaXN0Iiwia2luZCI6ImJvb2wiLCJpY29uIjoiaS1sdWNpZGUtbGlzdC12aWRlbyIsIm9yZGVyIjoxLCJleHRyYXMiOnt9LCJfdHlwZSI6ImRsX2ZpZWxkIiwiX3ZlcnNpb24iOiIxLjAifQ
```

</details>

3. Create a preset, and in the `CLI options` field set `--no-playlist`. Then select the preset, or use the following import string:

<details>
<summary>import as preset</summary>

```text
eyJuYW1lIjoibm9fcGxheWxpc3QiLCJjbGkiOiItLW5vLXBsYXlsaXN0IiwiX3R5cGUiOiJwcmVzZXQiLCJfdmVyc2lvbiI6IjIuNiJ9
```
</details>

# Install specific yt-dlp version?

You can force specific version of `yt-dlp` by setting the `YTP_YTDLP_VERSION` environment variable for example

```env
YTP_YTDLP_VERSION=2025.07.21 or master or nightly
```

Then restart the container to apply the changes.

# Custom output template placeholders

YTPTube supports custom `ytp_*` placeholders in `yt-dlp` output template via the following syntax `%(ytp_*:<args>)s`.

## Currently available extra placeholders are:

- `ytp_random`: random mixed letters and digits,
  - `N` A number is required to specify the length of the random string, for example `%(ytp_random:8)s` will generate a random string of 8 characters. 
  - if the args followed by `:s` it will generate random letters only, if followed by `:d` it will generate random digits only.

## Examples of the custom placeholders in action:

- Template: `%(title)s [%(ytp_random:8)s].%(ext)s`
  - Example result: `My Video [A7k2Pq9Z].mp4`
- Template: `%(uploader)s/%(ytp_random:6:d)s - %(title)s.%(ext)s`
  - Example result: `MyChannel/483920 - My Video.mp4`
- Template: `%(playlist)s/%(ytp_random:10:s)s/%(title)s.%(ext)s`
  - Example result: `Favorites/QwErTyUiOp/My Video.mp4`

> [!NOTE]
> `%(ytp_` placeholders are a YTPTube extension and not available via console or directly via yt-dlp.

# How can I monitor sites without RSS feeds?

See [Generic Task Definitions](docs/task-definitions.md) for complete documentation on how to create a generic task 
definition for sites.

# How to generate POT tokens?

You need a POT provider server. The `bgutil-ytdlp-pot-provider` extractor is already included. You can use this 
compose example:

<details>
<summary>POT provider Compose example</summary>

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}" # change this to your user id and group id, for example: "1000:1000"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads:rw
    tmpfs:
      - /tmp
    depends_on:
      - bgutil_provider
  bgutil_provider:
    init: true
    image: brainicism/bgutil-ytdlp-pot-provider:latest
    container_name: bgutil_provider
    restart: unless-stopped    
```

</details>

Then create a new preset, and in the `CLI options` field set the following:

```bash
--extractor-args "youtubepot-bgutilhttp:base_url=http://bgutil_provider:4416" 
```

See the [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) project.

# Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, please remember that YTPTube is only a wrapper for 
[yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, 
postprocessing, permissions, other `yt-dlp options` configurations which seem not to work, or anything else that 
concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project.

To debug these problems, first run the `yt-dlp` binary directly, bypassing the UI. Once the command works, import its
options into a new `preset`.

## Via HTTP

If you have enabled the web terminal with the `YTP_CONSOLE_ENABLED` environment variable, go to `Other > Terminal` and
run the `yt-dlp` command. You can also open the download form, click `advanced options`, and then click the 
yellow terminal icon, `Run directly in console`.

## Via CLI 

Assuming your YTPTube container is called `ytptube`, run the following on your docker host to get a shell inside the container:

```bash
docker exec -ti ytptube bash
cd /downloads
yt-dlp ....
```

Once there, you can use the yt-dlp command freely.

# Run behind reverse proxy.

A reverse proxy can provide additional authentication and/or HTTPS support for YTPTube.

## Caddy http server

The following example Caddyfile gets a reverse proxy going behind [caddy](https://caddyserver.com).

```caddyfile
# If you are using sub-domain.
# make sure to change "ytptube:8081" to the actual name of your YTPTube container/port.
ytp.example.org {
  reverse_proxy ytptube:8081
}

# If you are using sub-folder, for example: https://example.org/ytptube/
# Also make sure to set the `YTP_BASE_PATH` environment variable to `/ytptube/`
# make sure to change "ytptube:8081" to the actual name of your YTPTube container/port.
example.org {
  redir /ytptube /ytptube/
  route /ytptube/* {
    reverse_proxy ytptube:8081
  }
}
```

# How to autoload yt-dlp plugins?

To load yt-dlp plugins in YTPTube, create a folder named `yt-dlp` inside `/config`. The path will be `/config/yt-dlp`.
Follow the [yt-dlp plugins docs](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#plugins) to install the plugins.

Once you have installed the plugins, restart the container and the plugins will be auto-loaded on demand.

# How to load random backgrounds from WatchState or any other source?

YTPTube can pull random background images from different sources, including `WatchState`, another project of mine. Set the
`YTP_PICTURES_BACKENDS` environment variable to the following URL:

```env
YTP_PICTURES_BACKENDS=https://watchstate.ip/v1/api/system/images/background?apikey=[api_key]
```

Where `[api_key]` is the api key you get from your WatchState instance.

# How to use share folder or external storage as download target?

Mount the share folder as the target for `/downloads`. This can cause permission or cross-device link errors. To avoid
these issues, mount the share folder as a named volume, then mount the named volume at `/downloads/smb` or
`/downloads/nfs`.

<details>
<summary>External storage Compose example</summary>

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}" # change this to your user id and group id, for example: "1000:1000"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      # Config must be mounted locally as read-write sqlite doesn't support network mounts.
      - ./config:/config:rw
      # Mount a local directory
      - ./downloads:/downloads/local:rw
      # Mount the NFS share
      - nfs-data:/downloads/nfs:rw
      # Mount the SMB share
      - smb-data:/downloads/smb:rw
    tmpfs:
      - /tmp

volumes:
  nfs-data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=10.0.0.3,rw,nfsvers=4 # <--- Change server IP and options
      device: ":/exported/path" # <--- Remote NFS path
  
  smb-data:
    driver: local
    driver_opts:
      type: cifs
      o: username=my_username,password=my_password,vers=3.0,uid=1000,gid=1000,file_mode=0777,dir_mode=0777 # <--- Change options to fit your needs
      device: "//10.0.0.3/public" # <--- Remote SMB path
```

</details>

If you prefer, you can bypass YTPTube `download_path` and set it to `/` and completely manage your own mounts. However,
please be aware that the file browser feature will expose whatever `download_path` is set to. **So, if you set it to `/`, 
the file browser will expose the entire container filesystem.**

# The origin of the project.

The project first started as a fork [meTube](https://github.com/alexta69/metube), since then it has been completely 
rewritten and redesigned. The original project was a great starting point, but it didn't align with my vision for the 
project and what i wanted to achieve with it.
  
# How to use hardware acceleration for video transcoding?

As the container is rootless, we cannot do the necessary changes to the container to enable hardware acceleration.
However, We do have the drivers and ffmpeg already installed and the CPU transcoding should work regardless. To enable
hardware acceleration You need to alter your `compose.yaml` file to mount the necessary devices to the container. Here
is an example of how to do it for debian based systems.

<details>
<summary>Hardware acceleration Compose example</summary>

```yaml
services:
 ytptube:
    ........ # see above for the rest of the configuration
    devices:
       # Mount all DRI devices when the host has one GPU.
      - /dev/dri:/dev/dri                       
      # Otherwise, selectively mount the devices you need.
      - /dev/dri/card0      # Intel GPU device
      - /dev/dri/renderD128 # Intel GPU render node
    group_add:
      # Add the necessary groups to the container to access the gpu devices.
      - 44   # it might be different on your system.                                 
      - 105  # it might be different on your system.
```

</details>

This setup should enable VAAPI encoding in `x86_64` containers.

> [!NOTE]
> Your `video`, `render` group id might be different from mine, you can run the follow command in docker host server to get the group ids for both groups.

```bash
cat /etc/group | grep -E 'render|video'

video:x:44:your_docker_username
render:x:105:your_docker_username
```

In my docker host the group id for `video` is `44` and for `render` is `105`. change what needed in the `compose.yaml`
file to match your setup.

If for some reason the initial test for GPU encoding fails, YTPTube will fallback to software encoding. You can force
software encoding by setting the `YTP_STREAMER_VCODEC` environment variable to `libx264`. If you want to force GPU encoding, set the
`YTP_STREAMER_VCODEC` environment variable to one of the supported GPU codecs, for example `h264_vaapi` or `h264_nvenc` depending on your GPU.
For the supported codec implementations, see [segment_encoders.py](app/features/streaming/library/segment_encoders.py).

If GPU encoding fails and software encoding is used, restart the container before trying GPU encoding again. YTPTube
tests GPU encoding only once, when the first video stream starts.

# How to setup CI on Gitea?

The Docker container builder supports self-hosted repositories such as Gitea. Define two values in your repository
settings:

1. Create a secret named `GIT_TOKEN` and set it to your Gitea personal access token.
2. Create a variable named `REGISTRY` and set it to your docker registry, for example `gitea.domain.org`.

The `main.yml` workflow will then disable the Docker/GitHub container registries and use your Gitea repository instead.
The container name will be `REGISTRY/ytptube`, and the tags will match those used in the GitHub registry.

Unfortunately, the `native-builder.yml` workflow doesn't support self-hosted repositories at the moment.

# Getting No space left on device error

If you encounter this error: `OSError: [Errno 28] No space left on device` This indicates that either 
the `/tmp` or `/downloads` directory has run out of available space.

This issue commonly occurs when:

- `/tmp` is mounted as `tmpfs` (memory-based storage)
- Your system has limited RAM
- You're downloading large video files

Since videos are temporarily stored in `/tmp` before being moved to the final download location, memory-based storage 
may be insufficient for large downloads.

To fix the issue, modify your `compose.yaml` to use a disk-based directory for temporary files:

<details>
<summary>Temporary storage Compose example</summary>

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads/local:rw
      - ./temp:/tmp:rw
```

</details>

> [!NOTE]
> Replace the `tmpfs` mount with a local directory volume (`./temp:/tmp:rw`). This allows temporary files to use disk space instead of RAM.

Restart the container to apply the mount change. Temporary files will then use the mounted disk path instead of RAM.

# How to prevent loading screen during YouTube premieres?

During YouTube premieres, streams usually contain a loading screen of 1-5 minutes before the actual video content starts
playing. By default we wait for 5min + the duration of the video before starting the download to ensure we get the full video without
the loading screen. However, you can override the behavior by setting the following environment variable:

```env
YTP_LIVE_PREMIERE_BUFFER=10
```

Where `YTP_LIVE_PREMIERE_BUFFER` is the buffer time in minutes to add to the video duration before the download starts. 
This will help in case the premiere has a longer loading screen than usual.

# How to bypass some WAF challenges?

You need to setup [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) or a compatible alternative such as [Trawl](https://github.com/germondai/trawl) (which handles newer challenge formats) and then set the `YTP_FLARESOLVERR_URL` 
environment variable to point to your instance. For example:

<details>
<summary>FlareSolverr Compose example</summary>

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}" # change this to your user id and group id, for example: "1000:1000"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    environment:
      - YTP_FLARESOLVERR_URL=http://flaresolverr:8191/v1
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads:rw
    tmpfs:
      - /tmp
    depends_on:
      - flaresolverr
  flaresolverr:
    image: flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    restart: unless-stopped    
```

</details>

See the [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) and [Trawl](https://github.com/germondai/trawl)
projects.

# How to use the browser extractor?

Use this extractor when a site's media URL only appears after the page runs in a browser. Set `YTP_BROWSER_URL` to the
HTTP endpoint exposed by a remote Chromium instance:

```env
YTP_BROWSER_URL=http://chrome:9222
```

Select the `generic_browser` preset for downloads that need it. The preset forces yt-dlp's generic extractor, so do
not use it for sites supported by a dedicated extractor. The extractor waits up to 60 seconds for media. To use a
shorter limit, add this to the CLI options:

```bash
--extractor-args "generic:wait=30"
```

If the browser extractor fails, YTPTube falls back to the normal generic extractor.

## Example compose setup

<details>
<summary>Browser extractor Compose example</summary>

```yaml
services:
  chrome:
    image: jlesage/chromium:latest
    container_name: chrome
    environment:
      - CHROMIUM_REMOTE_DEBUGGING=1 # enable remote debugging
      - KEEP_APP_RUNNING=1
      - DISPLAY_WIDTH=1920
      - DISPLAY_HEIGHT=1080
  ytptube:
    user: "${UID:-1000}:${UID:-1000}"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    environment:
      - YTP_BROWSER_URL=http://chrome:9222
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads:rw
```

</details>

---

# How do I change the UI language?

YTPTube supports multiple languages with RTL support. Currently the following languages are available:

**Available languages:**
- English (default)
- العربية (Arabic, RTL)
- Français (French)
- 中文 (Chinese)
- 日本語 (Japanese)

**Changing the language:**

1. Open the **Settings** panel (gear icon in the sidebar).
2. Select your preferred language from the **Language** dropdown.
3. The UI updates immediately and your choice is saved in a browser cookie (`ytptube_locale`).

**Automatic detection:**

On first visit, YTPTube attempts to detect your browser's preferred language and switches automatically if a matching 
translation is available.
