# ACTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)

Web GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) with playlist & channel support. Allows you to download videos from YouTube and [dozens of other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

ACTube is a fork of [meTube](https://github.com/alexta69/metube) project by alexta69.

## Run using Docker

```bash
docker run -d --name ytptube -p 8081:8081 -v ./config:/config:rw -v /path/to/downloads:/downloads:rw ghcr.io/ArabCoders/ytptube
```

## Run using docker-compose

```yaml
version: "3"
services:
  ytptube:
    image: ghcr.io/ArabCoders/ytptube
    container_name: ytptube
    restart: unless-stopped
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
```

## Configuration via environment variables

Certain values can be set via environment variables, using the `-e` parameter on the docker command line, or the `environment:` section in docker-compose.

* __UID__: user under which ytptube will run. Defaults to `1000`.
* __GID__: group under which ytptube will run. Defaults to `1000`.
* __UMASK__: umask value used by ytptube. Defaults to `022`.
* __DEFAULT_THEME__: default theme to use for the UI, can be set to `light`, `dark` or `auto`. Defaults to `auto`.
* __DOWNLOAD_DIR__: path to where the downloads will be saved. Defaults to `/downloads` in the docker image, and `.` otherwise.
* __AUDIO_DOWNLOAD_DIR__: path to where audio-only downloads will be saved, if you wish to separate them from the video downloads. Defaults to the value of `DOWNLOAD_DIR`.
* __DOWNLOAD_DIRS_INDEXABLE__: if `true`, the download dirs (__DOWNLOAD_DIR__ and __AUDIO_DOWNLOAD_DIR__) are indexable on the web server. Defaults to `false`.
* __CUSTOM_DIRS__: whether to enable downloading videos into custom directories within the __DOWNLOAD_DIR__ (or __AUDIO_DOWNLOAD_DIR__). When enabled, a drop-down appears next to the Add button to specify the download directory. Defaults to `true`.
* __CREATE_CUSTOM_DIRS__: whether to support automatically creating directories within the __DOWNLOAD_DIR__ (or __AUDIO_DOWNLOAD_DIR__) if they do not exist. When enabled, the download directory selector becomes supports free-text input, and the specified directory will be created recursively. Defaults to `true`.
* __STATE_DIR__: path to where the queue persistence files will be saved. Defaults to `/config` in the docker image, and `.` otherwise.
* __TEMP_DIR__: path where intermediary download files will be saved. Defaults to `/downloads` in the docker image, and `.` otherwise. Set this to an SSD or RAM filesystem (e.g., `tmpfs`) for better performance __Note__: Using a RAM filesystem may prevent downloads from being resumed.
* __DELETE_FILE_ON_TRASHCAN__: if `true`, downloaded files are deleted on the server, when they are trashed from the "Completed" section of the UI. Defaults to `false`.
* __URL_PREFIX__: base path for the web server (for use when hosting behind a reverse proxy). Defaults to `/`.
* __OUTPUT_TEMPLATE__: the template for the filenames of the downloaded videos, formatted according to [this spec](https://github.com/yt-dlp/yt-dlp/blob/master/README.md#output-template). Defaults to `%(title)s.%(ext)s`.
* __OUTPUT_TEMPLATE_CHAPTER__: the template for the filenames of the downloaded videos, when split into chapters via postprocessors. Defaults to `%(title)s - %(section_number)s %(section_title)s.%(ext)s`.
* __YTDL_OPTIONS__: Additional options to pass to youtube-dl, in JSON format. [See available options here](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L183). They roughly correspond to command-line options, though some do not have exact equivalents here, for example `--recode-video` has to be specified via `postprocessors`. Also note that dashes are replaced with underscores.
* __YTDL_OPTIONS_FILE__: A path to a JSON file that will be loaded and used for populating `YTDL_OPTIONS` above. Please note that if both `YTDL_OPTIONS_FILE` and `YTDL_OPTIONS` are specified, the options in `YTDL_OPTIONS` take precedence.

The following example value for `YTDL_OPTIONS` embeds English subtitles and chapter markers (for videos that have them), and also changes the permissions on the downloaded video and sets the file modification timestamp to the date of when it was downloaded:

```yaml
    environment:
      - 'YTDL_OPTIONS={"writesubtitles":true,"subtitleslangs":["en","-live_chat"],"updatetime":false,"postprocessors":[{"key":"Exec","exec_cmd":"chmod 0664","when":"after_move"},{"key":"FFmpegEmbedSubtitle","already_have_subtitle":false},{"key":"FFmpegMetadata","add_chapters":true}]}'
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

## Using browser cookies

In case you need to use your browser's cookies with ytptube, for example to download restricted or private videos:

* Add the following to your docker-compose.yml:

```yaml
    volumes:
      - /path/to/cookies:/cookies
    environment:
      - YTDL_OPTIONS={"cookiefile":"/cookies/cookies.txt"}
```

* Install in your browser an extension to extract cookies:
  * [Firefox](https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/)
  * [Chrome](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
* Extract the cookies you need with the extension and rename the file `cookies.txt`
* Drop the file in the folder you configured in the docker-compose.yml above
* Restart the container

## Running behind a reverse proxy

It's advisable to run ytptube behind a reverse proxy, if authentication and/or HTTPS support are required.

When running behind a reverse proxy which remaps the URL (i.e. serves ytptube under a subdirectory and not under root), don't forget to set the URL_PREFIX environment variable to the correct value.

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

The engine which powers the actual video downloads in ytptube is [yt-dlp](https://github.com/yt-dlp/yt-dlp). Since video sites regularly change their layouts, frequent updates of yt-dlp are required to keep up.

There's an automatic nightly build of ytptube which looks for a new version of yt-dlp, and if one exists, the build pulls it and publishes an updated docker image. Therefore, in order to keep up with the changes, it's recommended that you update your ytptube container regularly with the latest image.

I recommend installing and setting up [watchtower](https://github.com/containrrr/watchtower) for this purpose.

## Troubleshooting and submitting issues

Before asking a question or submitting an issue for ytptube, please remember that ytptube is only a UI for [yt-dlp](https://github.com/yt-dlp/yt-dlp). Any issues you might be experiencing with authentication to video websites, postprocessing, permissions, other `YTDL_OPTIONS` configurations which seem not to work, or anything else that concerns the workings of the underlying yt-dlp library, need not be opened on the ytptube project. In order to debug and troubleshoot them, it's advised to try using the yt-dlp binary directly first, bypassing the UI, and once that is working, importing the options that worked for you into `YTDL_OPTIONS`.

In order to test with the yt-dlp command directly, you can either download it and run it locally, or for a better simulation of its actual conditions, you can run it within the ytptube container itself. Assuming your ytptube container is called `ytptube`, run the following on your Docker host to get a shell inside the container:

```bash
docker exec -ti ytptube sh
cd /downloads
```

Once there, you can use the yt-dlp command freely.

## Building and running locally

Make sure you have node.js and Python 3.8 installed.

```bash
cd ytptube/ui
# install Angular and build the UI
npm install
node_modules/.bin/ng build
# install python dependencies
cd ..
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# run
python app/main.py
```

A Docker image can be built locally (it will build the UI too):

```bash
docker build -t ytptube .
```
