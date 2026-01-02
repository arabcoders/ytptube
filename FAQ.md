# Environment variables

Certain configuration values can be set via environment variables, using the `-e` parameter on the docker command line, 
or the `environment:` section in `compose.yaml` file.

| Environment Variable            | Description                                                         | Default               |
| ------------------------------- | ------------------------------------------------------------------- | --------------------- |
| TZ                              | The timezone to use for the application                             | `(not_set)`           |
| YTP_OUTPUT_TEMPLATE             | The template for the filenames of the downloaded videos             | `%(title)s.%(ext)s`   |
| YTP_DEFAULT_PRESET              | The default preset to use for the download                          | `default`             |
| YTP_INSTANCE_TITLE              | The title of the instance                                           | `(not_set)`           |
| YTP_FILE_LOGGING                | Whether to log to file                                              | `false`               |
| YTP_DOWNLOAD_PATH               | Path to where the downloads will be saved                           | `/downloads`          |
| YTP_MAX_WORKERS                 | The maximum number of workers to use for downloading                | `20`                  |
| YTP_MAX_WORKERS_PER_EXTRACTOR   | The maximum number of concurrent downloads per extractor            | `2`                   |
| YTP_AUTH_USERNAME               | Username for basic authentication                                   | `(not_set)`           |
| YTP_AUTH_PASSWORD               | Password for basic authentication                                   | `(not_set)`           |
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
| YTP_UI_UPDATE_TITLE             | Whether to update the title of the page with the current stats      | `true`                |
| YTP_PIP_PACKAGES                | A space separated list of pip packages to install                   | `(not_set)`           |
| YTP_PIP_IGNORE_UPDATES          | Do not update the custom pip packages                               | `false`               |
| YTP_PICTURES_BACKENDS           | A comma separated list of pictures urls to use                      | `(not_set)`           |
| YTP_BROWSER_CONTROL_ENABLED     | Whether to enable the file browser actions                          | `false`               |
| YTP_YTDLP_AUTO_UPDATE           | Whether to enable the auto update for yt-dlp                        | `true`                |
| YTP_YTDLP_DEBUG                 | Whether to turn debug logging for the internal `yt-dlp` package     | `false`               |
| YTP_YTDLP_VERSION               | The version of yt-dlp to use. Defaults to latest version            | `(not_set)`           |
| YTP_FLARESOLVERR_URL            | FlareSolverr endpoint URL.                                          | `(not_set)`           |
| YTP_FLARESOLVERR_MAX_TIMEOUT    | Max FlareSolverr challenge timeout in seconds                       | `120`                 |
| YTP_FLARESOLVERR_CLIENT_TIMEOUT | HTTP client timeout (seconds) when calling FlareSolverr             | `120`                 |
| YTP_FLARESOLVERR_CACHE_TTL      | The cache TTL (in seconds) for FlareSolverr solutions               | `600`                 |
| YTP_BASE_PATH                   | Set this if you are serving YTPTube from sub-folder                 | `/`                   |
| YTP_PREVENT_LIVE_PREMIERE       | Prevents the initial youtube premiere stream from being downloaded  | `false`               |
| YTP_LIVE_PREMIERE_BUFFER        | buffer time in minutes to add to video duration                     | `5`                   |
| YTP_TASKS_HANDLER_TIMER         | The cron expression for the tasks handler timer                     | `15 */1 * * *`        |
| YTP_PLAYLIST_ITEMS_CONCURRENCY  | The number of playlist items be to processed at same time           | `1`                   |
| YTP_TEMP_DISABLED               | Disable temp files handling.                                        | `false`               |
| YTP_DOWNLOAD_PATH_DEPTH         | How many subdirectories to show in auto complete.                   | `1`                   |
| YTP_ALLOW_INTERNAL_URLS         | Allow requests to internal URLs                                     | `false`               |
| YTP_SIMPLE_MODE                 | Switch default interface to Simple mode.                            | `false`               |
| YTP_STATIC_UI_PATH              | Path to custom static UI files.                                     | `(not_set)`           |
| YTP_AUTO_CLEAR_HISTORY_DAYS     | Number of days after which completed download history is cleared.   | `0`                   |
| YTP_DEFAULT_PAGINATION          | The default number of items per page for history.                   | `50`                  |
| YTP_TASK_HANDLER_RANDOM_DELAY   | The maximum random delay in seconds before starting a task handler. | `60`                  |

> [!NOTE]
> To raise the maximum workers for specific extractor, you need to add a ENV variable that follows the pattern `YTP_MAX_WORKERS_FOR_<EXTRACTOR_NAME>`.
> The extractor name must be in uppercase, to know the extractor name, check the log for the specific extractor used for the download.
> The limit should not exceed the `YTP_MAX_WORKERS` value as it will be ignored.

> [!IMPORTANT]
> The env variable `YTP_SIMPLE_MODE` only control what being displayed for first time visitor, the users can still switch between the two modes via the WebUI settings page.

## Notes about YTP_AUTO_CLEAR_HISTORY_DAYS

- `0` days means no automatic clearing of the download history. lowest value that will trigger the clearing is `1` day.
- This setting will **NOT** delete the downloaded files, it will only clear the history from the database.

# Browser extensions & bookmarklets

## Simple bookmarklet

```javascript
javascript:(() => { const url = "https://ytp.example.org"; const preset = "default"; const mUrl = new URL(url);mUrl.pathname="/api/history/add";mUrl.searchParams.set("url",document.location.href);mUrl.searchParams.set("preset",preset);fetch(mUrl,{method: "GET"}).then(j => j.json()).then(json =>alert(json.message)).catch(err =>alert(err)); })()
```

Change the the variable `url` and `preset` variables to match your YTPTube instance and preset name.

> [!NOTE]
> The bookmarklet should be served from https page, otherwise, some browsers will block the request. for mixed content.

## Browser stores

- For Firefox via [Firefox Store](https://addons.mozilla.org/en-US/firefox/addon/ytptube-extension/)
- For Chrome/Chromium Browsers via [Chrome Store](https://chromewebstore.google.com/detail/ytptube-extension/kiepfnpeflemfokokgjiaelddchglfil)

## iOS Shortcuts

You can download [Add To YTPTube](https://www.icloud.com/shortcuts/18b8f70666a04a06aed09424f97ce951) shortcut and use it to send links to your YTPTube instance.
You have to edit the shortcut and replace the following:

- `https://ytp.example.org` with your YTPTube instance.
- `username:password` replace this with your own username & password or leave it empty if you don't have authentication enabled.

This shortcut is powerful, as it's allow you to select your preset on the fly pulled directly from your instance.
Combined with the new and powerful presets system, you could add presets for specific websites that need cookies,
and use that preset to download directly from your iOS device.

### Advanced iOS Shortcut

This shortcut [YTPTube To Media](https://www.icloud.com/shortcuts/6e3db0bd532843e3aec70e6ce211be08) is more advanced, as it's parses
the `yt-dlp` output and attempt to download the media directly to your iOS device. It doesn't always work, but it's a good
starting point for those who want to download media directly to their iOS device. We provide no support for this use case
other than the shortcut itself. this shortcut missing support for parsing the http_headers, it's only parse the cookies.

# Authentication

To enable basic authentication, set the `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` environment variables. And restart 
the container. This will prompt the user to enter the username and password before accessing the web interface/API.
As this is a simple basic authentication, if your browser doesn't show the prompt, you can use the following URL

`http://username:password@your_ytptube_url:port`

# I cant download anything

If you are receiving errors like:
- "OSError: [Errno 5] I/O error"
- "OSError: [Errno 18] Cross-device link: '/tmp/random_id/name.webm' -> '/downloads/name.webm'
- "Operation not permitted: '/downloads/name.webm'

This indicates an error with your mounts and how they interact with the container. So, the basic solution is to do the following:

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

Then run the following command to create the necessary directories and start the container:

```bash
mkdir -p ./config && mkdir -p ./downloads/{tmp,files} && docker compose -f compose.yaml up -d
```

Reference: [Issue #363](https://github.com/arabcoders/ytptube/issues/363)

# I want to use link with playlist but only download the video not all the videos in the playlist?

Simply create a preset, and in the `Command options for yt-dlp` field set `--no-playlist`. Then select the preset 
whenever the link includes a playlist id.

> [!NOTE]
> You can also do the same via advanced options `Command options for yt-dlp` field, but presets are more convenient.

# Install specific yt-dlp version?

You can force specific version of `yt-dlp` by setting the `YTP_YTDLP_VERSION` environment variable for example

```env
YTP_YTDLP_VERSION=2025.07.21 or master or nightly
```

Then restart the container to apply the changes.

# How can I monitor sites without RSS feeds?

YTPTube includes a **generic task handler** that turns JSON definition files into site-specific scrapers. You can use it
to watch pages that do not expose RSS or public APIs and automatically enqueue new links into the download queue.

1. Create definition files under `/config/tasks/*.json` (for Docker this is the mounted `config/tasks/` folder).
2. Keep your scheduled task in `tasks.json` pointing at the page you want to monitor and make sure it uses a preset that
   enables a download archive (`--download-archive`).
3. When the task runs, the handler scans the JSON files, picks the first definition whose `match` rule covers the task
   URL, fetches the page, extracts items, and queues the unseen ones.

### Definition schema

Each file must contain a single JSON object with the following keys:

```json5
{
  "name": "example",                  // Friendly identifier shown in logs
  "match": [
    "https://example.com/articles/*", // Glob strings, or objects with {"regex": "..."} or {"glob": "..."}
    { "regex": "https://example.com/post/[0-9]+" }
  ],
  "engine": {                         // Optional, defaults to HTTPX
    "type": "httpx",                  // "httpx" (default) or "selenium"
    "options": {
      "url": "http://selenium:4444/wd/hub", // Selenium-only: remote hub URL
      "arguments": ["--headless", "--disable-gpu"],
      "wait_for": { "type": "css", "expression": ".article" },
      "wait_timeout": 15,
      "page_load_timeout": 60
    }
  },
  "request": {                      // Optional HTTP settings
    "method": "GET",                // GET or POST
    "url": "https://example.com/articles/latest", // Override the task URL if needed
    "headers": { "User-Agent": "MyAgent/1.0" },
    "params": { "page": 1 },
    "data": null,
    "json": null,
    "timeout": 30
  },
  "response": {                      // Optional: how to interpret the body
    "type": "html"                   // "html" (default) or "json"
  },
  "parse": {
    "items": {                        // Optional container for per-item extraction
      "selector": ".columns .card",   // Defaults to CSS; set "type": "xpath" to use XPath
      "fields": {
        "link": {                     // Required inside fields: the per-item URL
          "type": "css",
          "expression": ".card-header a",
          "attribute": "href"
        },
        "title": {
          "type": "css",
          "expression": ".card-header a",
          "attribute": "text"
        },
        "poet": {
          "type": "css",
          "expression": "footer .card-footer-item:first-child a",
          "attribute": "text"
        }
      }
    },
    "page_title": {                    // Optional global field outside the container
      "type": "css",
      "expression": "title",
      "attribute": "text"
    }
  }
}
```

For JSON endpoints, switch the response format and use `jsonpath` selectors:

```json5
{
  "response": { "type": "json" },
  "parse": {
    "items": {
      "type": "jsonpath",
      "selector": "items",
      "fields": {
        "link": { "type": "jsonpath", "expression": "url" },
        "title": { "type": "jsonpath", "expression": "title" }
      }
    }
  }
}
```

### Parsing rules

- Every definition must provide a `link` field either at the top level or inside `parse.items.fields`. Other fields are optional metadata attached to the queued item.
- CSS and XPath rules may specify `attribute`:
  - `text` / `inner_text` applies `normalize-space()`.
  - `html` / `outer_html` returns the raw HTML fragment.
  - Any other value reads that attribute from the element. When omitted, the handler uses text and, for `link`, falls
    back to `href` automatically.
- Regex rules scan the HTML fragment associated with the current scope (page-level or container). Set `attribute` to a named/numbered capture group or rely on the first group.
- `post_filter` lets you run a final regex on the extracted value and pick a named (`value`) group.
- When you declare `parse.items`, each matching container is processed independently so missing fields in one card do not shift values for the rest.
- For JSON responses (`response.type = "json"`), set the container `type` and field `type` to `jsonpath` and supply [JMESPath](https://jmespath.org/) expressions. Relative values are resolved against each container object and converted to strings automatically.

### Fetch engines

- **httpx (default)**: supports custom headers, query params, JSON/body payloads, proxy inherited from the task preset,
  and optional timeout.
- **selenium**: uses a remote Chrome session. Provide the hub URL under `engine.options.url`; only Chrome is supported at
  the moment. Optional keys: `arguments` (list or string), `wait_for` (type `css`/`xpath` + `expression`), `wait_timeout`,
  and `page_load_timeout`.

Definitions are reloaded automatically when files change, so you can tweak them without restarting YTPTube. Check
`var/config/tasks/01-*.json` for sample files.

> [!NOTE]
> A machine-readable schema is available at `app/schema/task_definition.json` if you want to validate your JSON with editors or CI tools.

# How to generate POT tokens?

You need a pot provider server we already have the extractor `bgutil-ytdlp-pot-provider` pre-installed in the container.
You can simply do the following to enable the support for it.

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

Then simply create a new preset, and in the `Command options for yt-dlp` field set the following:

```bash
--extractor-args "youtubepot-bgutilhttp:base_url=http://bgutil_provider:4416" 
--extractor-args "youtube:player-client=default,tv,mweb;formats=incomplete"
```

you and also enable the fallback by using the follow extractor args

```bash
--extractor-args "youtubepot-bgutilhttp:base_url=http://bgutil_provider:4416;disable_innertube=1"
--extractor-args "youtube:player-client=default,tv,mweb;formats=incomplete"
```

Use this alternative extractor args in case the extractor fails to get the pot tokens from the bgutil provider server. 
For more information please visit [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) project.

# Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, please remember that YTPTube is only a thin wrapper for 
[yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, 
postprocessing, permissions, other `yt-dlp options` configurations which seem not to work, or anything else that 
concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project.

In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, 
and once that is working, importing the options that worked for you into a new `preset`.

## Via HTTP

If you have enabled the web terminal via `YTP_CONSOLE_ENABLED` environment variable, simply go to `Other > Terminal` use
 the yt-dlp command, the interface is jailed to the `yt-dlp` binary you can't access anything else.

## Via CLI 

Assuming your YTPTube container is called `ytptube`, run the following on your docker host to get a shell inside the container:

```bash
docker exec -ti ytptube bash
cd /downloads
yt-dlp ....
```

Once there, you can use the yt-dlp command freely.

# Run behind reverse proxy.

It's advisable to run YTPTube behind a reverse proxy, if better authentication and/or HTTPS support are required.

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

Loading yt-dlp plugins in YTPTube is quite simple, we already have everything setup for you. simply, create a folder 
inside the `/config` directory named `yt-dlp` so, the path will be `/config/yt-dlp`. then follow 
[yt-dlp plugins docs](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#plugins) to know how to install the plugins.

Once you have installed the plugins, restart the container and the plugins will be auto-loaded on demand.

# How to load random backgrounds from WatchState or any other source?

YTPTube can be configured to pull random background images from different sources, including `WatchState` which is another 
project of mine, simply change the `YTP_PICTURES_BACKENDS` environment variable to the following url

```env
YTP_PICTURES_BACKENDS=https://watchstate.ip/v1/api/system/images/background?apikey=[api_key]
```

Where `[api_key]` is the api key you get from your WatchState instance.

# How to use share folder or external storage as download target?

You can simply mount the share folder as target for `/downloads` path, but in some cases you might face issues with permissions or
cross-device link errors. To avoid these issues, you can mount the share folder as a named volume, and then mount the 
named volume to `/downloads/smb` or `/downloads/nfs`.

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

```yaml
services:
 ytptube:
    ........ # see above for the rest of the configuration
    devices:
      # mount the dri devices to the container if you only have one gpu you can simply do the following
      - /dev/dri:/dev/dri                       
      # Otherwise, selectively mount the devices you need.
      - /dev/dri/card0      # Intel GPU device
      - /dev/dri/renderD128 # Intel GPU render node
    group_add:
      # Add the necessary groups to the container to access the gpu devices.
      - 44   # it might be different on your system.                                 
      - 105  # it might be different on your system.
```

This setup should work for at VAAPI encoding in `x86_64` containers.

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
For more information about the supported codecs, please refer to the [SegmentEncoders.py](app/library/SegmentEncoders.py) file.

If GPU encoding fails and software encoding is used, you will have to restart the container to try GPU encoding again. 
as we only test for GPU encoding once on first video stream.

# Allowing internal URLs requests

By default, YTPTube prevents requests to internal resources, for security reasons. However, if you want to allow requests to internal URLs, you can set the `YTP_ALLOW_INTERNAL_URLS` environment variable to `true`. This will allow requests to internal URLs. 

We do not recommend enabling this option unless you know what you are doing, as it can expose your internal network to 
potential security risks. This should only be used if it's truly needed.

# How to setup CI on Gitea?

The docker container builder already support self-hosted repositories like Gitea, you simply need to define two things at your repository settings.

1. Create a secret named `GIT_TOKEN` and set it to your Gitea personal access token.
2. Create a variable named `REGISTRY` and set it to your docker registry, for example `gitea.domain.org`.

Thats it, the `main.yml` will now disable the docker/github container registries, and use your Gitea repository instead. It will follow the usual
naming, your container name will be named `REGISTRY/ytptube` and the tags will be the same as the ones used in the github registry.

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

> [!NOTE]
> Replace the `tmpfs` mount with a local directory volume (`./temp:/tmp:rw`). This allows temporary files to use disk space instead of RAM.

After making the changes, restart your container. This should resolve the "No space left on device" 
error during download.


# How to prevent loading screen during YouTube premieres?

Depending on how you look at it, YTPTube live download implementation is rather great and fast. However, during YouTube 
premieres, usually streams will contain a loading screen of say, 1-5 minutes before the actual video content starts 
playing. By default we wait for 5min + the duration of the video before starting the download to ensure we get the full video without
the loading screen. However, you can override the behavior by setting the following environment variable:

```env
YTP_PREVENT_LIVE_PREMIERE=true
YTP_LIVE_PREMIERE_BUFFER=10
```

Where `YTP_LIVE_PREMIERE_BUFFER` is the buffer time in minutes to add to the video duration before the download starts. 
This will help in case the premiere has a longer loading screen than usual.

# How to bypass CF challenges?

You need to setup [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) and then set the `YTP_FLARESOLVERR_URL` 
environment variable to point to your FlareSolverr instance. For example:

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

For more information please visit [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) project.
