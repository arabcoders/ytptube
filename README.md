# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support.

YTPTube started as a fork of [meTube](https://github.com/alexta69/metube), Since then it went under heavy changes, and it supports many new features.

# YTPTube Features.
* Multi-downloads support.
* Handle live streams.
* Schedule Channels or Playlists to be downloaded automatically at a specific time.
* Send notification to targets based on specified events. 
* Support per link `yt-dlp JSON config or cli options`, `cookies` & `output format`.
* Queue multiple URLs separated by comma.
* A built in video player that can play any video file regardless of the format. **With support for sidecar external subtitles**.
* New `POST /api/history` endpoint that allow one or multiple links to be sent at the same time.
* New `GET /api/history/add?url=http://..` endpoint that allow to add single item via GET request.
* Completely redesigned the frontend UI.
* Switched out of binary file storage in favor of SQLite.
* Basic Authentication support.
* Support for curl_cffi, see [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#impersonation)
* Support for both advanced and basic mode for WebUI.

For more API endpoints, please refer to the [API documentation](API.md).
    
### Tips
Your `yt-dlp` config should include the following options for optimal working conditions.

```json
{
  "windowsfilenames": true,
  "continue_dl": true,
  "live_from_start": true,
  "format_sort": [ "codec:avc:m4a" ],
}
```
* Note, the `format_sort`, forces YouTube to use x264 instead of vp9 codec, you can ignore it if you want. i prefer the media in x264.

[![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_short.png)](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_full.png)

## Run using Docker

```bash
docker run -d --rm --name ytptube -p 8081:8081 -v ./config:/config:rw -v ./downloads:/downloads:rw ghcr.io/arabcoders/ytptube
```

## Run using compose file.

```yaml
services:
  ytptube:
    user: "1000:1000"
    image: ghcr.io/arabcoders/ytptube
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

## Environment variables

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

## Bookmarklets and browser extensions

### For simple bookmarklets

```javascript
javascript:(() => { const url = "https://ytptube.example.org"; const preset = "default"; const mUrl = new URL(url); mUrl.pathname = "/api/history"; fetch(mUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: document.location.href, preset: preset }) }).then(res => alert(res.ok ? "URL sent!" : "Failed to send URL.")); })()
```

Change the the variable `url` and `preset` variables to match your YTPTube instance and preset name.

### Browser Extensions Store

- For Firefox via [Firefox Store](https://addons.mozilla.org/en-US/firefox/addon/ytptube-extension/)
- For Chrome/Chromium Browsers via [Chrome Store](https://chromewebstore.google.com/detail/ytptube-extension/kiepfnpeflemfokokgjiaelddchglfil)

### iOS Shortcuts

not yet available.


## Running behind a reverse proxy

It's advisable to run YTPTube behind a reverse proxy, if authentication and/or HTTPS support are required.

### NGINX

```nginx
location /ytptube/ {
  proxy_pass http://ytptube:8081;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
}
```

Note: the extra `proxy_set_header` directives are there to make web socket connection work.

### Caddy

The following example Caddyfile gets a reverse proxy going behind [caddy](https://caddyserver.com).

```caddyfile
example.com {
  route /ytptube/* {
    uri strip_prefix ytptube
    reverse_proxy ytptube:8081
  }
}
```

## Updating yt-dlp

The engine which powers the actual video downloads in YTPTube is [yt-dlp](https://github.com/yt-dlp/yt-dlp). Since video sites regularly change their layouts, frequent updates of yt-dlp are required to keep up.

There's an automatic nightly build of YTPTube which looks for a new version of yt-dlp, and if one exists, the build pulls it and publishes an updated docker image. Therefore, in order to keep up with the changes, it's recommended that you update your YTPTube container regularly with the latest image.

## Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, please remember that YTPTube is only a UI for [yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, postprocessing, permissions, other `yt-dlp options` configurations which seem not to work, or anything else that concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project. In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, and once that is working, importing the options that worked for you into `yt-dlp options` file.

In order to test with the yt-dlp command directly, you can either download it and run it locally, or for a better simulation of its actual conditions, you can run it within the YTPTube container itself. 

#### Via HTTP

Simply go to `Console` button in your navbar and directly use the yt-dlp command.

#### Via CLI 

Assuming your YTPTube container is called `ytptube`, run the following on your Docker host to get a shell inside the container:

```bash
docker exec -ti ytptube bash
cd /downloads
yt-dlp ....
```

Once there, you can use the yt-dlp command freely.

## Building and running locally

Make sure you have `nodejs` and `Python 3.11+` installed.

```bash
cd ytptube/frontend
# install Vue and build the UI
npm install
npm run build
# install python dependencies
cd ..
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

## ytdlp.json file

The `config/ytdlp.json`, is a json file which can be used to alter the default `yt-dlp` config settings globally. 
We recommend not use this file for options that aren't **truly global**, everything that can be done via the `ytdlp.json` file
can be done via a preset, which only effects the download that uses it. For example, my personal preset that i use for all
my jp video downloads is:

```json5
{
  "name": "jp_videos",
  "format": "bv[ext=mp4]+(ba[ext=m4a][format_note*=original]/ba)/bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
  "args": {
    "writesubtitles": true,
    "writeinfojson": true,
    "writethumbnail": true,
    "merge_output_format": "mkv",
    "final_ext": "mkv",
    "format_sort": [ "codec:avc:m4a" ],
    "subtitleslangs": [ "en", "ar" ]
  },
  "postprocessors": [
    {
      "key": "FFmpegVideoRemuxer",
      "preferedformat": "mkv"
    },
    {
      "key": "FFmpegConcat",
      "only_multi_video": true,
      "when": "playlist"
    },
    {
      "key": "FFmpegThumbnailsConvertor",
      "format": "jpg"
    },
    {
      "key": "FFmpegSubtitlesConvertor",
      "format": "srt"
    },
    {
      "key": "FFmpegMetadata",
      "add_chapters": true,
      "add_infojson": true,
      "add_metadata": true
    },
    {
      "key": "FFmpegEmbedSubtitle",
      "already_have_subtitle": false
    },
    {
      "key": "Exec",
      "exec_cmd": "/usr/bin/mkvpropedit %(filepath)q --edit track:a1 --set language=jpn --set name=Japanese --add-track-statistics-tags",
      "when": "after_move"
    }
  ]
}
```

You can convert your own yt-dlp command arguments into a preset using the box found in the presets add page. For reference, 
The options can be found at [yt-dlp YoutubeDL.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L214) file.
And for the postprocessors at [yt-dlp postprocessor](https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/postprocessor).

## Authentication

To enable basic authentication, set the `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` environment variables. And restart the container.
This will prompt the user to enter the username and password before accessing the web interface/API.
As this is a simple basic authentication, if your browser doesn't show the prompt, you can use the following URL

`http://username:password@your_ytptube_url:port`


## Basic mode

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

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 
I Personally don't need the money, but I do appreciate the gesture. Making a child happy is more worthwhile.
