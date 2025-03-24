# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support.

[![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_short.png)](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_full.png)

# YTPTube Features.

* Multi-downloads support.
* Random beautiful background. `can be disabled`.
* Can Handle live streams.
* Scheduler to queue channels or playlists to be downloaded automatically at a specified time.
* Send notification to targets based on selected events. 
* Support per link `yt-dlp JSON config or cli options`, `cookies` & `output format`.
* Queue multiple URLs separated by comma.
* A built in video player that can play any video file regardless of the format. **With support for sidecar external subtitles**.
* New `POST /api/history` endpoint that allow one or multiple links to be sent at the same time.
* New `GET /api/history/add?url=http://..` endpoint that allow to add single item via GET request.
* Modern frontend UI.
* SQLite as database backend.
* Basic Authentication support.
* Support for curl_cffi, see [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#impersonation)
* Support for both advanced and basic mode for WebUI.
* Bundled tools in container: curl-cffi, ffmpeg, ffprobe, aria2, rtmpdump, mkvtoolsnix, mp4box.
    
# Recommended basic `ytdlp.json` file settings

Your `/config/ytdlp.json` config should include the following basic options for optimal working conditions.

```json
{
  "windowsfilenames": true,
  "continue_dl": true,
  "live_from_start": true,
  "format_sort": [ "codec:avc:m4a" ],
}
```

> [!NOTE]
> Note, the `format_sort`, forces YouTube to use x264 instead of vp9 codec, you can ignore it if you want. i prefer the media in x264.

# Run using docker command

```bash
docker run -d --rm --name ytptube -p 8081:8081 -v ./config:/config:rw -v ./downloads:/downloads:rw ghcr.io/arabcoders/ytptube:latest
```

# Using compose file

The following is an example of a `compose.yaml` file that can be used to run YTPTube.

```yaml
services:
  ytptube:
    user: "1000:1000" # change this to your user id and group id
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

```bash
$ mkdir {config,downloads} && docker-compose -f compose.yaml up -d
```

Then you can access the WebUI at `http://localhost:8081`.

# Environment variables

Certain configuration values can be set via environment variables, using the `-e` parameter on the docker command line, or the `environment:` section in `compose.yaml` file.

| Environment Variable     | Description                                                      | Default                            |
| ------------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| YTP_OUTPUT_TEMPLATE      | The template for the filenames of the downloaded videos          | `%(title)s.%(ext)s`                |
| YTP_DEFAULT_PRESET       | The default preset to use for the download                       | `default`                          |
| YTP_INSTANCE_TITLE       | The title of the instance                                        | `empty string`                     |
| YTP_FILE_LOGGING         | Whether to log to file                                           | `false`                            |
| YTP_DOWNLOAD_PATH        | Path to where the downloads will be saved                        | `/downloads`                       |
| YTP_MAX_WORKERS          | How many works to use for downloads                              | `1`                                |
| YTP_AUTH_USERNAME        | Username for basic authentication                                | `empty string`                     |
| YTP_AUTH_PASSWORD        | Password for basic authentication                                | `empty string`                     |
| YTP_CONSOLE_ENABLED      | Whether to enable the console                                    | `false`                            |
| YTP_REMOVE_FILES         | Remove the actual file when clicking the remove button           | `false`                            |
| YTP_CONFIG_PATH          | Path to where the queue persistence files will be saved          | `/config`                          |
| YTP_TEMP_PATH            | Path where intermediary download files will be saved             | `/tmp`                             |
| YTP_TEMP_KEEP            | Whether to keep the Individual video temp directory or remove it | `false`                            |
| YTP_KEEP_ARCHIVE         | Keep history of downloaded videos                                | `true`                             |
| YTP_YTDL_DEBUG           | Whether to turn debug logging for the internal `yt-dlp` package  | `false`                            |
| YTP_ALLOW_MANIFESTLESS   | Allow `yt-dlp` to download unprocessed streams                   | `false`                            |
| YTP_HOST                 | Which IP address to bind to                                      | `0.0.0.0`                          |
| YTP_PORT                 | Which port to bind to                                            | `8081`                             |
| YTP_LOG_LEVEL            | Log level                                                        | `info`                             |
| YTP_STREAMER_VCODEC      | The video codec to use for in-browser streaming                  | `libx264`                          |
| YTP_STREAMER_ACODEC      | The audio codec to use for in-browser streaming                  | `aac`                              |
| YTP_ACCESS_LOG           | Whether to log access to the web server                          | `true`                             |
| YTP_DEBUG                | Whether to turn on debug mode                                    | `false`                            |
| YTP_DEBUGPY_PORT         | The port to use for the debugpy debugger                         | `5678`                             |
| YTP_SOCKET_TIMEOUT       | The timeout for the yt-dlp socket connection variable            | `30`                               |
| YTP_EXTRACT_INFO_TIMEOUT | The timeout for extracting video information                     | `70`                               |
| YTP_DB_FILE              | The path to the SQLite database file                             | `{config_path}/ytptube.db`         |
| YTP_MANUAL_ARCHIVE       | The path to the manual archive file                              | `{config_path}/manual_archive.log` |
| YTP_UI_UPDATE_TITLE      | Whether to update the title of the page with the current stats   | `true`                             |
| YTP_PIP_PACKAGES         | A space separated list of pip packages to install                | `empty string`                     |
| YTP_PIP_IGNORE_UPDATES   | Do not update the custom pip packages                            | `false`                            |
| YTP_BASIC_MODE           | Whether to run WebUI in basic mode                               | `false`                            |

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

It's advisable to run YTPTube behind a reverse proxy, if authentication and/or HTTPS support are required.

### Nginx http server

```nginx
location /ytptube/ {
  proxy_pass http://ytptube:8081;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
}
```

> [!NOTE]
> The extra `proxy_set_header` directives are there to make web socket connection work.

### Caddy http server

The following example Caddyfile gets a reverse proxy going behind [caddy](https://caddyserver.com).

```caddyfile
example.com {
  route /ytptube/* {
    uri strip_prefix ytptube
    reverse_proxy ytptube:8081
  }
}
```

# Updating yt-dlp

The engine which powers the actual video downloads in YTPTube is [yt-dlp](https://github.com/yt-dlp/yt-dlp). Since video sites regularly change their layouts, frequent updates of yt-dlp are required to keep up.

There's an automatic nightly task YTPTube which looks for a new version of yt-dlp, and if one exists, it will be open PR on the repository. The PR will be reviewed and merged by the maintainer.

# Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, Please remember that YTPTube is only a UI for [yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, postprocessing, permissions, other `yt-dlp options` configurations which seem not to work, or anything else that concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project. In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, and once that is working, importing the options that worked for you into `yt-dlp options` file.

In order to test with the yt-dlp command directly, you can either download it and run it locally, or for a better simulation of its actual conditions, you can run it within the YTPTube container itself. 

## Via HTTP

If you have enabled the web terminal via `YTP_CONSOLE_ENABLED` environment variable, simply go to `Terminal` button in 
your navbar and directly use the yt-dlp command, the interface is jailed to the `yt-dlp` binary you can't access the
anything else.

## Via CLI 

Assuming your YTPTube container is called `ytptube`, run the following on your docker host to get a shell inside the container:

```bash
docker exec -ti ytptube bash
cd /downloads
yt-dlp ....
```

Once there, you can use the yt-dlp command freely.

# Building and running locally

> [!IMPORTANT]
> Make sure you have `nodejs` and `Python 3.11+` installed.

Follow these steps to build and run YTPTube locally:

```bash
cd ytptube/ui
# install Vue and build the UI
npm install
npm run build
# install python dependencies
cd ..
# you might not have venv module installed, if so, install it via `pip3 install venv` or your package manager.
python -m venv .venv
source .venv/bin/activate
pip3 install pipenv
pipenv install
# run
python app/main.py
```

A Docker image can be built locally (it will build the UI too):

```bash
docker build . -t ytptube
```

# ytdlp.json file

The `config/ytdlp.json`, is a json file which can be used to alter the default `yt-dlp` config settings globally. 

We recommend not use this file for options that aren't **truly global**, everything that can be done via the `ytdlp.json` file
can be done via a preset, which only effects the download that uses it. Example of good basic `ytdlp.json` file.

```json
{
  "windowsfilenames": true,
  "continue_dl": true,
  "live_from_start": true,
  "format_sort": [ "codec:avc:m4a" ],
}
```

Everything else can be done via the presets, and it's more flexible and easier to manage. You can convert your 
own yt-dlp command arguments into a preset using the box found in the presets add page. For reference, The options can be found
at [yt-dlp YoutubeDL.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L214) file. And for the postprocessors at [yt-dlp postprocessor](https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/postprocessor).

# Authentication

To enable basic authentication, set the `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` environment variables. And restart the container.
This will prompt the user to enter the username and password before accessing the web interface/API.
As this is a simple basic authentication, if your browser doesn't show the prompt, you can use the following URL

`http://username:password@your_ytptube_url:port`


# Basic mode

What does the basic mode do? it hides the the following features from the WebUI.

### Header

It disables everything except the `theme switcher` and `reload` button.

### Add form 

* The form will always be visible and un-collapsible.
* Everything except the `URL` and `Add` button will be disabled and hidden.
* The preset will be the default preset, which can be specified via `YTP_DEFAULT_PRESET` environment variable.
* The output template will be the default template which can be specified via `YTP_OUTPUT_TEMPLATE` environment variable.
* The download path will be the default download path which can be specified via `YTP_DOWNLOAD_PATH` environment variable.

### Queue & History

Disables the `Information` button.

# API Documentation

For API endpoints, please refer to the [API documentation](API.md). it's somewhat outdated, but it's a good starting point.

# How to autoload yt-dlp plugins?

Loading yt-dlp plugin in YTPTube is is quite simple, we already have everything setup for you. simply, create a folder 
inside the `/config` directory named `yt-dlp` so, the path will be `/config/yt-dlp`. then follow 
[yt-dlp plugins docs](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#plugins) to know how to install the plugins.

Once you have installed the plugins, restart the container and the plugins will be auto-loaded on demand.

# The origin of the project.

The project first started as a fork [meTube](https://github.com/alexta69/metube), since then it has been completely 
rewritten and redesigned. The original project was a great starting point, but it didn't align with my vision for the 
project and what i wanted to achieve with it.

# Disclaimer

This project is not affiliated with YouTube, yt-dlp, or any other service. It's a personal project that was created to
make downloading videos from the internet easier. It's not intended to be used for piracy or any other illegal activities.

# Project plan

Let me start by saying, i am primarily PHP developer, and i am not familiar with the best practices of python or frontend design.

There are no project plan, or design document for this project. I started this project as a hobby project, and i am learning
as i go. What you see is the result of me learning while creating this tool. It might not be the best but i like it.

While i value your feedback, remember this project is a hobby project, and i may not have the time to implement all the
features you might want. I am open to PRs, and i will do my best to review them and merge them if they fit my vision for the
project.

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 

