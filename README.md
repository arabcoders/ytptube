# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support. Allows you to download videos from YouTube and [dozens of other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

YTPTube is a fork of [meTube](https://github.com/alexta69/metube) project by alexta69.

## Run using Docker

```bash
docker run -d --name ytptube -p 8081:8081 -v ./config:/config:rw -v ./downloads:/downloads:rw ghcr.io/arabcoders/ytptube
```

## Run using docker-compose

```yaml
version: "3"
services:
  ytptube:
    user: "1000:1000"
    image: ghcr.io/arabcoders/ytptube
    container_name: ytptube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config
      - ./downloads:/downloads
```

## Configuration via environment variables

Certain values can be set via environment variables, using the `-e` parameter on the docker command line, or the `environment:` section in docker-compose.

* __UMASK__: umask value used by YTPTube. Defaults to `022`.
* __YTP_CONFIG_PATH__: path to where the queue persistence files will be saved. Defaults to `/config` in the docker image, and `./var/config` otherwise.
* __YTP_DOWNLOAD_PATH__: path to where the downloads will be saved. Defaults to `/downloads` in the docker image, and `./var/downloads` otherwise.
* __YTP_TEMP_PATH__: path where intermediary download files will be saved. Defaults to `/downloads` in the docker image, and `./var/tmp` otherwise. Set this to an SSD or RAM filesystem (e.g., `tmpfs`) for better performance __Note__: Using a RAM filesystem may prevent downloads from being resumed.
* __YTP_URL_PREFIX__: base path for the web server (for use when hosting behind a reverse proxy). Defaults to `/`.
* __YTP_OUTPUT_TEMPLATE__: the template for the filenames of the downloaded videos, formatted according to [this spec](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#output-template). Defaults to `%(title)s.%(ext)s`.
* __YTP_YTDL_OPTIONS__: Additional options to pass to yt-dlp, in JSON format. [See available options here](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L183). They roughly correspond to command-line options, though some do not have exact equivalents here, for example `--recode-video` has to be specified via `postprocessors`. Also note that dashes are replaced with underscores.
* __YTP_YTDL_OPTIONS_FILE__: A path to a JSON file that will be loaded and used for populating `YTDL_OPTIONS` above.

The following example value for `YTDL_OPTIONS` embeds English subtitles and chapter markers (for videos that have them), and also changes the permissions on the downloaded video and sets the file modification timestamp to the date of when it was downloaded:

```yaml
    environment:
      - 'YTP_YTDL_OPTIONS={"writesubtitles":true,"subtitleslangs":["en","-live_chat"],"updatetime":false,"postprocessors":[{"key":"Exec","exec_cmd":"chmod 0664","when":"after_move"},{"key":"FFmpegEmbedSubtitle","already_have_subtitle":false},{"key":"FFmpegMetadata","add_chapters":true}]}'
```

The following example value for `OUTPUT_TEMPLATE` sets:
- playlist name and author, if present
- playlist number and count, if present (zero-padded, if needed)
- video author, title and release date in YYYY-MM-DD format, falling back to *UNKNOWN_...* if missing
- sanitizes everything for valid UNIX filename

```yaml
    environment:
      - 'OUTPUT_TEMPLATE=%(playlist_title&Playlist |)S%(playlist_title|)S%(playlist_uploader& by |)S%(playlist_uploader|)S%(playlist_autonumber& - |)S%(playlist_autonumber|)S%(playlist_count& of |)S%(playlist_count|)S%(playlist_autonumber& - |)S%(uploader,creator|UNKNOWN_AUTHOR)S - %(title|UNKNOWN_TITLE)S - %(release_date>%Y-%m-%d,upload_date>%Y-%m-%d|UNKNOWN_DATE)S.%(ext)s'
```

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

I recommend installing and setting up [watchtower](https://github.com/containrrr/watchtower) for this purpose.

## Troubleshooting and submitting issues

Before asking a question or submitting an issue for YTPTube, please remember that YTPTube is only a UI for [yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, postprocessing, permissions, other `YTDL_OPTIONS` configurations which seem not to work, or anything else that concerns the workings of the underlying yt-dlp library, need not be opened on the YTPTube project. In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, and once that is working, importing the options that worked for you into `YTDL_OPTIONS`.

In order to test with the yt-dlp command directly, you can either download it and run it locally, or for a better simulation of its actual conditions, you can run it within the YTPTube container itself. Assuming your YTPTube container is called `YTPTube`, run the following on your Docker host to get a shell inside the container:

```bash
docker exec -ti ytptube sh
cd /downloads
```

Once there, you can use the yt-dlp command freely.

## Building and running locally

Make sure you have node.js and Python 3.8 installed.

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
docker build -t ytptube .
```
