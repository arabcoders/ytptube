# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support.

YTPTube started as a fork of [meTube](https://github.com/alexta69/metube), Since then it went under heavy changes, and it supports many new features.

# YTPTube Features.
* A built in video player that can play any video file regardless of the format. **With support for sidecar external subtitles**.
* New `/add_batch` endpoint that allow multiple links to be sent.
* Completely redesigned the frontend UI.
* Switched out of binary file storage in favor of SQLite.
* Handle live streams.
* Support per link, `yt-dlp config` and `cookies`. and `output format`.
* Tasks Runner. It allow you to queue channels for downloading using simple `json` file.
* Webhook sender. It allow you to add webhook endpoints that receive events related to downloads using simple `json` file.
* Multi-downloads support.
* Queue multiple URLs separated by comma.
* Basic Authentication support.
* Support for curl_cffi, see [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#impersonation)
    
### Tips
Your `yt-dlp` config should include the following options for optimal working conditions.

```json
{
    "windowsfilenames": true,
    "live_from_start": true,
    "format_sort": [
        "codec:avc:m4a"
    ]
}
```
* Note, the `format_sort`, forces YouTube to use x264 instead of vp9 codec, you can ignore it if you want. i prefer the media in x264.

[![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_short.png)](https://raw.githubusercontent.com/ArabCoders/ytptube/master/sc_full.png)

## Run using Docker

```bash
docker run -d --name ytptube -p 8081:8081 -v ./config:/config:rw -v ./downloads:/downloads:rw ghcr.io/arabcoders/ytptube
```

## Run using docker-compose

```yaml
version: "3.9"
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

## Configuration via environment variables

Certain values can be set via environment variables, using the `-e` parameter on the docker command line, or the `environment:` section in docker-compose.

* __YTP_CONFIG_PATH__: path to where the queue persistence files will be saved. Defaults to `/config` in the docker image, and `./var/config` otherwise.
* __YTP_DOWNLOAD_PATH__: path to where the downloads will be saved. Defaults to `/downloads` in the docker image, and `./var/downloads` otherwise.
* __YTP_TEMP_PATH__: path where intermediary download files will be saved. Defaults to `/tmp` in the docker image, and `./var/tmp` otherwise.
* __YTP_TEMP_KEEP__: Whether to keep the Individual video temp directory or remove it. Defaults to `false`.
* __YTP_URL_PREFIX__: base path for the web server (for use when hosting behind a reverse proxy). Defaults to `/`.
* __YTP_OUTPUT_TEMPLATE__: the template for the filenames of the downloaded videos, formatted according to [this spec](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#output-template). Defaults to `%(title)s.%(ext)s`. This will be the default for all downloads unless the request include output template.
* __YTP_OUTPUT_TEMPLATE_CHAPTER__: the template for the filenames of the downloaded videos, when split into chapters via postprocessors, formatted according to [this spec](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#output-template). Defaults to `%(title)s - %(section_number)s %(section_title)s.%(ext)s.`
* __YTP_KEEP_ARCHIVE__: Whether to keep history of downloaded videos to prevent downloading same file multiple times. Defaults to `true`.
* __YTP_YTDL_DEBUG__: Whether to turn debug logging for the internal `yt-dlp` package. Defaults to `false`.
* __YTP_ALLOW_MANIFESTLESS__: Allow `yt-dlp` to download live streams videos which are yet to be processed by YouTube. Defaults to `false`
* __YTP_HOST__: Which IP address to bind to. Defaults to `0.0.0.0`.
* __YTP_PORT__: Which port to bind to. Defaults to `8081`.
* __YTP_LOG_LEVEL__: Log level. Defaults to `info`.
* __YTP_MAX_WORKERS__: How many works to use for downloads. Defaults to `1`.
* __YTP_STREAMER_VCODEC__: The video codec to use for in-browser streaming. Defaults to `libx264`.
* __YTP_STREAMER_ACODEC__: The audio codec to use for in-browser streaming. Defaults to `aac`.
* __YTP_AUTH_USERNAME__: Username for basic authentication. Defaults open for all
* __YTP_AUTH_PASSWORD__: Password for basic authentication. Defaults open for all.
* __YTP_REMOVE_FILES__: Whether to remove the actual downloaded file when clicking the remove button. Defaults to `false`.
* __YTP_ACCESS_LOG__: Whether to log access to the web server. Defaults to `true`.
* __YTP_DEBUG__: Whether to turn on debug mode. Defaults to `false`.
* __YTP_DEBUGPY_PORT__: The port to use for the debugpy debugger. Defaults to `5678`.
* __YTP_SOCKET_TIMEOUT__: The timeout for the yt-dlp socket connection variable. Defaults to `30`.
* __YTP_EXTRACT_INFO_TIMEOUT__: The timeout for extracting video information. Defaults to `70`.
* __YTP_DB_FILE__: The path to the SQLite database file. Defaults to `{config_path}/ytptube.db`.
* __YTP_MANUAL_ARCHIVE__: The path to the manual archive file. Defaults to `{config_path}/manual_archive.log`.
* __YTP_UI_UPDATE_TITLE__: Whether to update the title of the page with the current stats. Defaults to `true`.
* __YTP_PIP_PACKAGES__: a space separated list of pip packages to install. Defaults to `""`, you can also use `{config_path}/pip.txt` to install the packages.
* __YTP_PIP_IGNORE_UPDATES__: Do not update the custom pip packages. Defaults to `false`.

## Running behind a reverse proxy

It's advisable to run YTPTube behind a reverse proxy, if authentication and/or HTTPS support are required.

When running behind a reverse proxy which remaps the URL (i.e. serves YTPTube under a subdirectory and not under root), don't forget to set the `YTP_URL_PREFIX` environment variable to the correct value.

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

### ytdlp.json File

The `config/ytdlp.json`, is a json file which can be used to alter the default `yt-dlp` config settings. For example these are the options i personally use,

```json5
{
  // Make the final filename windows compatible.
  "windowsfilenames": true,
  // Write subtitles if the stream has them.
  "writesubtitles": true,
  // Write info.json file for each download. It can be used by many tools to generate info etc.
  "writeinfojson": true,
  // Write thumbnail if available.
  "writethumbnail": true,
  // Do not download automatically generated subtitles. 
  "writeautomaticsub": false,
  // MP4 is limited with the codecs we use, so "mkv" make sense.
  "merge_output_format": "mkv",
  // Record live stream from the start.
  "live_from_start": true,
  // For YouTube try to force H264 video codec & AAC audio.
  "format_sort": [
      "codec:avc:m4a"
  ],
  // Your choice of subtitle languages to download.
  "subtitleslangs": [ "en", "ar" ],
  // postprocessors to run on the file
  "postprocessors": [
      // this processor convert the downloaded thumbnail to jpg.
      {
          "key": "FFmpegThumbnailsConvertor",
          "format": "jpg"
      },
      // This processor convert subtitles to srt format.
      {
          "key": "FFmpegSubtitlesConvertor",
          "format": "srt"
      },
      // This processor embed metadata & info.json file into the final mkv file.
      {
          "key": "FFmpegMetadata",
          "add_infojson": true,
          "add_metadata": true
      },
      // This process embed subtitles into the final file if it doesn't have subtitles embedded.
      {
          "key": "FFmpegEmbedSubtitle",
          "already_have_subtitle": false
      }
  ]
}
``` 

### tasks.json File

The `config/tasks.json`, is a json file, which can be used to queue URLs for downloading, it's mainly useful if you follow specific channels and you want it downloaded automatically, The schema for the file is as the following, Only the `URL` key is required.

```json5
[
  {
    // (URL: string) **REQUIRED**, URL to the content.
    "url": "", 
    // (Name: string) Optional field. Mainly used for logging. If omitted, random GUID will be shown.
    "name": "My super secret channel", 
    // (Timer: string) Optional field. Using regular cronjob timer, if the field is omitted, it will run every hour in random minute.
    "timer": "1 */1 * * *", 
    // (yt-dlp cookies: object) Optional field. A JSON cookies exported by flagCookies.
    "ytdlp_cookies": {}, 
    // (yt-dlp config: object) Optional field. A JSON yt-dlp config.
    "ytdlp_config": {},
    // (Output Template: string) Optional field. A File output format,
    "output_template": "",
    // (Folder: string) Optional field. Where to store the downloads relative to the main download path.
    "folder":"",
    // (Format: string) Optional field. Format as specified in Web GUI. Defaults to "any".
    "format": "",
    // (Quality: string), Optional field. Quality as specified in Web GUI. Defaults to "best".
    "quality": "", 
  },
  {
   // (URL: string) **REQUIRED**, URL to the content.
   "url": "https://..." // This is valid config, it will queue the channel for downloading every hour at random minute.
  },
  ...
]
```

The task runner is doing what you are doing when you click the add button on the WebGUI, this just fancy way to automate that.

**WARNING**: We strongly advice turning on `YTP_KEEP_ARCHIVE` option. Otherwise, you will keep re-downloading the items, and you will eventually get banned from the source or or you will waste space, bandwidth re-downloading content over and over.

### webhooks.json File

The `config/webhooks.json`, is a json file, which can be used to add webhook endpoints that would receive events related to the downloads.

```json5
[
  {
    // (name: string) - REQUIRED - The webhook name.
    "name": "my very smart webhook receiver",
    // (on: array) - OPTIONAL - List of accepted events, if left empty it will send all events.
    // Allowed events ["added", "completed", "error", "not_live" ] you can choose one or all of them.
    "on": [ "added", "completed", "error", "not_live" ],
    "request": {
      // (url: string) - REQUIRED-  The webhook url
      "url": "https://mysecert.webhook.com/endpoint", 
      // (type: string) - OPTIONAL - The request type, it can be json or form.
      "type": "json",
      // (method: string) - OPTIONAL - The request method, it can be POST or PUT
      "method": "POST",
      // (headers: dictionary) - OPTIONAL - Extra headers to include.
      "headers": {
        "Authorization": "Bearer my_secret_token"
      }
  }
  ...
]
```

## Authentication

To enable basic authentication, set the `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` environment variables. And restart the container.
This will prompt the user to enter the username and password before accessing the web interface/API.
As this is a simple basic authentication, if your browser doesn't show the prompt, you can use the following URL

`http://username:password@your_ytptube_url:port`

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 
I Personally don't need the money, but I do appreciate the gesture. Making a child happy is more worthwhile.
