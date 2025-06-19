# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

**YTPTube** is a web-based GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp), designed to make downloading videos from 
YouTube and other video platforms easier and more user-friendly. It supports downloading playlists, channels, and 
live streams, and includes features like scheduling downloads, sending notifications, and a built-in video player.

![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_short.png)

# YTPTube Features.

* Multi-downloads support.
* Random beautiful background. `can be disabled or source changed`.
* Can handle live streams.
* Scheduler to queue channels or playlists to be downloaded automatically at a specified time.
* Send notification to targets based on selected events. 
* Support per link `cli options` & `cookies`.
* Queue multiple URLs separated by comma.
* Presets system to re-use frequently used yt-dlp options.
* Simple file browser. `Disabled by default`.
* A built in video player **with support for sidecar external subtitles**.
* New `POST /api/history` endpoint that allow one or multiple links to be sent at the same time.
* New `GET /api/history/add?url=http://..` endpoint that allow to add single item via GET request.
* Modern frontend UI.
* SQLite as database backend.
* Basic authentication support.
* Support for curl_cffi, see [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#impersonation)
* Support basic mode for WebUI for non-technical users, which hides most of the normal features from view.
* Bundled tools in container: curl-cffi, ffmpeg, ffprobe, aria2, rtmpdump, mkvtoolsnix, mp4box.
* Automatic upcoming live stream re-queue.
* Apply `yt-dlp` options per custom defined conditions.
* Custom browser extensions, bookmarklets and iOS shortcuts to send links to YTPTube instance.

# Installation

## Run using docker command

```bash
mkdir -p ./{config,downloads} && docker run -d --rm --user "$UID:${GID-$UID}" --name ytptube \
-p 8081:8081 -v ./config:/config:rw -v ./downloads:/downloads:rw \
ghcr.io/arabcoders/ytptube:latest
```

Then you can access the WebUI at `http://localhost:8081`.

> [!NOTE]
> If you are using `podman` instead of `docker`, you can use the same command, but you need to change the user to `0:0`
> it will appears to be running as root, but it will run as the user who started the container.

## Using compose file

The following is an example of a `compose.yaml` file that can be used to run YTPTube.

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
```

> [!IMPORTANT]
> Make sure to change the `user` line to match your user id and group id

```bash
$ mkdir -p ./{config,downloads} && docker compose -f compose.yaml up -d
```

Then you can access the WebUI at `http://localhost:8081`.

> [!NOTE]
> you can use podman-compose instead of docker-compose, as it supports the same syntax. However, you should change the 
> user to `0:0` it will appears to be running as root, but it will run as the user who started the container.

## Unraid

For `Unraid` users You can install the `Community Applications` plugin, and search for **ytptube** it comes 
pre-configured.

# Browser extensions & bookmarklets

## Simple bookmarklet

```javascript
javascript:(() => { const url = "https://ytptube.example.org"; const preset = "default"; const mUrl = new URL(url); mUrl.pathname = "/api/history"; fetch(mUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: document.location.href, preset: preset }) }).then(res => alert(res.ok ? "URL sent!" : "Failed to send URL.")); })()
```

Change the the variable `url` and `preset` variables to match your YTPTube instance and preset name.

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

# Updating yt-dlp

The engine which powers the actual video downloads in YTPTube is [yt-dlp](https://github.com/yt-dlp/yt-dlp). Since video 
sites regularly updated, frequent updates of yt-dlp are required to keep up.

We have added the `YTP_YTDLP_AUTO_UPDATE` environment variable, which is enabled by default. This feature allows the 
container to automatically update `yt-dlp` to the latest version whenever the container starts. If a new version is 
available, it will be downloaded and applied automatically. To disable this automatic update, set the 
`YTP_YTDLP_AUTO_UPDATE` environment variable to `false`.

We will no longer release new versions of YTPTube for every new version of yt-dlp.

# Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, please remember that YTPTube is only a thin wrapper for 
[yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, 
postprocessing, permissions, other `yt-dlp options` configurations which seem not to work, or anything else that 
concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project.

In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, 
and once that is working, importing the options that worked for you into a new `preset` or `ytdlp.cli` file.

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

# ytdlp.cli file

The `config/ytdlp.cli`, is a command line options file for `yt-dlp` it will be globally applied to all downloads.

We strongly recommend not use this file for options that aren't **truly global**, everything that can be done via the 
file can also be done via the presets which is dynamic can be altered per download. Example of good global options 
are to be used for all downloads are:

```bash
--continue --windows-filenames --live-from-start
```

Everything else can be done via the presets, and it's more flexible and easier to manage.

# Authentication

To enable basic authentication, set the `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` environment variables. And restart 
the container. This will prompt the user to enter the username and password before accessing the web interface/API.
As this is a simple basic authentication, if your browser doesn't show the prompt, you can use the following URL

`http://username:password@your_ytptube_url:port`

# Basic mode

What does the basic mode do? it hides the the following features from the WebUI.

### Header

It disables everything except the `settings button` and `reload` button.

### Add form 

* Disable Everything except the `URL` and `Add`.
* The form will always be visible and un-collapsible.
* The preset will be the default preset, which can be specified via `YTP_DEFAULT_PRESET` environment variable.
* The output template will be the default template which can be specified via `YTP_OUTPUT_TEMPLATE` environment variable.
* The download path will be the default download path which can be specified via `YTP_DOWNLOAD_PATH` environment variable.

### Queue & History

Disables the `Information` button.

# API Documentation

For simple API documentation, you can refer to the [API documentation](API.md).

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

# The origin of the project.

The project first started as a fork [meTube](https://github.com/alexta69/metube), since then it has been completely 
rewritten and redesigned. The original project was a great starting point, but it didn't align with my vision for the 
project and what i wanted to achieve with it.

# Disclaimer

This project is not affiliated with YouTube, yt-dlp, or any other service. It's a personal project that was created to
make downloading videos from the internet easier. It's not intended to be used for piracy or any other illegal activities.

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 

# Environment variables

Certain configuration values can be set via environment variables, using the `-e` parameter on the docker command line, or the `environment:` section in `compose.yaml` file.

| Environment Variable           | Description                                                        | Default                            |
| ------------------------------ | ------------------------------------------------------------------ | ---------------------------------- |
| YTP_OUTPUT_TEMPLATE            | The template for the filenames of the downloaded videos            | `%(title)s.%(ext)s`                |
| YTP_DEFAULT_PRESET             | The default preset to use for the download                         | `default`                          |
| YTP_INSTANCE_TITLE             | The title of the instance                                          | `empty string`                     |
| YTP_FILE_LOGGING               | Whether to log to file                                             | `false`                            |
| YTP_DOWNLOAD_PATH              | Path to where the downloads will be saved                          | `/downloads`                       |
| YTP_MAX_WORKERS                | How many works to use for downloads                                | `1`                                |
| YTP_AUTH_USERNAME              | Username for basic authentication                                  | `empty string`                     |
| YTP_AUTH_PASSWORD              | Password for basic authentication                                  | `empty string`                     |
| YTP_CONSOLE_ENABLED            | Whether to enable the console                                      | `false`                            |
| YTP_REMOVE_FILES               | Remove the actual file when clicking the remove button             | `false`                            |
| YTP_CONFIG_PATH                | Path to where the config files will be stored.                     | `/config`                          |
| YTP_TEMP_PATH                  | Path to where tmp files are stored.                                | `/tmp`                             |
| YTP_TEMP_KEEP                  | Whether to keep the Individual video temp directory or remove it   | `false`                            |
| YTP_KEEP_ARCHIVE               | Keep history of downloaded videos                                  | `true`                             |
| YTP_YTDL_DEBUG                 | Whether to turn debug logging for the internal `yt-dlp` package    | `false`                            |
| YTP_HOST                       | Which IP address to bind to                                        | `0.0.0.0`                          |
| YTP_PORT                       | Which port to bind to                                              | `8081`                             |
| YTP_LOG_LEVEL                  | Log level                                                          | `info`                             |
| YTP_STREAMER_VCODEC            | The video codec to use for in-browser streaming                    | `libx264`                          |
| YTP_STREAMER_ACODEC            | The audio codec to use for in-browser streaming                    | `aac`                              |
| YTP_ACCESS_LOG                 | Whether to log access to the web server                            | `true`                             |
| YTP_DEBUG                      | Whether to turn on debug mode                                      | `false`                            |
| YTP_DEBUGPY_PORT               | The port to use for the debugpy debugger                           | `5678`                             |
| YTP_SOCKET_TIMEOUT             | The timeout for the yt-dlp socket connection variable              | `30`                               |
| YTP_EXTRACT_INFO_TIMEOUT       | The timeout for extracting video information                       | `70`                               |
| YTP_DB_FILE                    | The path to the SQLite database file                               | `{config_path}/ytptube.db`         |
| YTP_MANUAL_ARCHIVE             | The path to the manual archive file                                | `{config_path}/manual_archive.log` |
| YTP_UI_UPDATE_TITLE            | Whether to update the title of the page with the current stats     | `true`                             |
| YTP_PIP_PACKAGES               | A space separated list of pip packages to install                  | `empty string`                     |
| YTP_PIP_IGNORE_UPDATES         | Do not update the custom pip packages                              | `false`                            |
| YTP_BASIC_MODE                 | Whether to run WebUI in basic mode                                 | `false`                            |
| YTP_PICTURES_BACKENDS          | A comma separated list of pictures urls to use.                    | `empty string`                     |
| YTP_BROWSER_ENABLED            | Whether to enable the file browser                                 | `false`                            |
| YTP_YTDLP_AUTO_UPDATE          | Whether to enable the auto update for yt-dlp                       | `true`                             |
| YTP_BASE_PATH                  | Set this if you are serving YTPTube from sub-folder                | `/`                                |
| YTP_PREVENT_LIVE_PREMIERE      | Prevents the initial youtube premiere stream from being downloaded | `false`                            |
| YTP_TASKS_HANDLER_TIMER        | The cron expression for the tasks handler timer.                   | `15 */1 * * *`                     |
| YTP_PLAYLIST_ITEMS_CONCURRENCY | The number of playlist items be to processed at same time.         | `1`                                |

