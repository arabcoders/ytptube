# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support. Allows you to download videos from YouTube and [dozens of other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

YTPTube started as a fork of [meTube](https://github.com/alexta69/metube) project by alexta69. Since then it went under heavy changes, and it supports many new features.

# YTPTube Features compared to meTube.
* A built in video player that can play any video file regardless of the format.
* New `/add_batch` endpoint that allow multiple links to be sent.
* Re-Imagined the frontend and re-wrote the code in VueJS.
* Switched out of binary file storage in favor of SQLite.
* Handle live streams.
* Support per link, `yt-dlp config` and `cookies`. and `output format`
* Tasks Runner. It allow you to queue channels for downloading using simple `json` file for configuration.

### Tips
Your `yt-dlp` config should include the following options for optimal working conditions.

```json
{
    "windowsfilenames": true,
    "continue_dl": true,
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

* __UMASK__: umask value used by YTPTube. Defaults to `022`.
* __YTP_CONFIG_PATH__: path to where the queue persistence files will be saved. Defaults to `/config` in the docker image, and `./var/config` otherwise.
* __YTP_DOWNLOAD_PATH__: path to where the downloads will be saved. Defaults to `/downloads` in the docker image, and `./var/downloads` otherwise.
* __YTP_TEMP_PATH__: path where intermediary download files will be saved. Defaults to `/tmp` in the docker image, and `./var/tmp` otherwise.
* __YTP_URL_PREFIX__: base path for the web server (for use when hosting behind a reverse proxy). Defaults to `/`.
* __YTP_OUTPUT_TEMPLATE__: the template for the filenames of the downloaded videos, formatted according to [this spec](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#output-template). Defaults to `%(title)s.%(ext)s`. This will be the default for all downloads unless the request include output template.
* __YTP_YTDL_OPTIONS_FILE__: A path to a JSON file that will be loaded and used for populating `ytdlp options`.
* __YTP_KEEP_ARCHIVE__: Whether to keep history of downloaded videos to prevent downloading same file multiple times. Defaults to `false`.

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

Note: the extra `proxy_set_header` directives are there to make WebSocket work.

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

In order to test with the yt-dlp command directly, you can either download it and run it locally, or for a better simulation of its actual conditions, you can run it within the YTPTube container itself. Assuming your YTPTube container is called `YTPTube`, run the following on your Docker host to get a shell inside the container:

```bash
docker exec -ti ytptube sh
cd /downloads
```

Once there, you can use the yt-dlp command freely.

## Building and running locally

Make sure you have node.js and Python 3.11 installed.

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

### tasks.json File

The `config/tasks.json`, is a json file, which can be used to queue URLs for downloading, it's mainly useful if you follow specific channels and you want it downloaded automatically, The schema for the file is as the following, Only the `URL` key is required.

```json
[
  {
    "url": "", // (URL: string) **REQUIRED**, URL to the content.
    "name": "My super secret channel", // (Name: string) Optional field. Mainly used for logging. If omitted, random GUID will be shown.
    "timer": "1 */1 * * *", // (Timer: string) Optional field. Using regular cronjob timer, if the field is omitted, it will run every hour in random minute.
    "ytdlp_cookies": {}, // (yt-dlp cookies: object) Optional field. A JSON cookies exported by flagCookies.
    "ytdlp_config": {}, // (yt-dlp config: object) Optional field. A JSON yt-dlp config.
    "output_template": "", // (Output Template: string) Optional field. A File output format,
    "folder":"", // (Folder: string) Optional field. Where to store the downloads relative to the main download path.
    "format": "", // (Format: string) Optional field. Format as specified in Web GUI. Defaults to "any".
    "quality": "", // (Quality: string), Optional field. Quality as specified in Web GUI. Defaults to "best".
  },
  {
    "url": "https://..." // This is valid config, it will queue the channel for downloading every hour at random minute.
  },
  ...
]
```

The task runner is doing what you are doing when you click the add button on the WebGUI, this just fancy way to automate that.

**WARNING**: We strongly advice turning on `YTP_KEEP_ARCHIVE` option. Otherwise, you will keep re-downloading the items, and you will eventually get banned from the source or or you will waste space, bandwidth re-downloading content over and over.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 
I Personally don't need the money, but I do appreciate the gesture. Making a child happy is more worthwhile.
