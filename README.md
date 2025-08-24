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
* Send notification to targets based on selected events. includes [Apprise](https://github.com/caronc/apprise?tab=readme-ov-file#readme) support for non http/https URLs.
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
* A executable for Windows, macOS and Linux, which can be found in the release page.

Please read the [FAQ](FAQ.md) for more information.

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

# API Documentation

For simple API documentation, you can refer to the [API documentation](API.md).

# Disclaimer

This project is not affiliated with YouTube, yt-dlp, or any other service. It's a personal project that was created to
make downloading videos from the internet easier. It's not intended to be used for piracy or any other illegal activities.

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 
