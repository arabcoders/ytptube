# YTPTube

![Build Status](https://github.com/ArabCoders/ytptube/actions/workflows/main.yml/badge.svg)
![MIT License](https://img.shields.io/github/license/arabcoders/ytptube.svg)
![Docker pull](https://ghcr-badge.elias.eu.org/shield/arabcoders/ytptube/ytptube)

**YTPTube** is a web-based GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp), designed to make downloading videos from 
video platforms easier and user-friendly. It supports downloading playlists, channels, live streams and 
includes features like scheduling downloads, sending notifications, and built-in video player.

# Screenshots
Example of the regular view interface.
![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/dev/sc_short.jpg)

Example of the Simple mode interface.
![Short screenshot](https://raw.githubusercontent.com/ArabCoders/ytptube/dev/sc_simple.jpg)

# YTPTube Features.

* Multi-download support.
* Random beautiful background.
* Handles live and upcoming streams.
* A dual view mode for both technical and non-technical users.
* Schedule channels or playlists to be downloaded automatically with support for creating custom download feeds from non-supported sites. See [Feeds documentation](FAQ.md#how-can-i-monitor-sites-without-rss-feeds).
* Send notification to targets based on selected events. includes [Apprise](https://github.com/caronc/apprise?tab=readme-ov-file#readme) support.
* Support per link options.
* Support for limits per extractor and overall global limit.
* Queue multiple URLs at once.
* Powerful presets system for applying `yt-dlp` options. with a pre-made preset for media servers users.
* A simple file browser.
* A built in video player **with support for sidecar external subtitles**. `Require ffmpeg to be in PATH in non-docker setups`.
* Basic authentication support.
* Supports `curl-cffi`. See [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#impersonation). `In docker only`.
* Bundled `pot provider plugin`. See [yt-dlp documentation](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide). `In docker only`.
* Automatic updates for `yt-dlp` and custom `pip` packages. `In docker only`.
* Conditions feature to apply custom options based on `yt-dlp` returned info.
* Custom browser extensions, bookmarklets and iOS shortcuts to send links to YTPTube instance.
* A bundled executable version for Windows, macOS and Linux. `MacOS version is untested`.

Please read the [FAQ](FAQ.md) for more information.

# Installation

## Run using docker command

```bash
mkdir -p ./{config,downloads} && docker run -d --rm --user "${UID}:${UID}" --name ytptube \
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
> If you have low RAM, remove the `tmpfs` and mount a disk-based directory to `/tmp` instead. See [FAQ](FAQ.md#getting-no-space-left-on-device-error) for more information.

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

This project is not affiliated with yt-dlp or any other service.

It’s a personal project designed to make downloading videos from the internet more convenient. It’s not intended for 
piracy or any unlawful use.

This project was built primarily for my own needs and preferences. The UI might not be the most polished or visually 
refined, but I’m happy with it as it is. You can, however, create and load your own UI for complete customization. I 
plan to refactor the UI/UX in the future using [Nuxt/ui](https://ui.nuxt.com/).

Contributions are welcome, but I may decline changes that don’t align with my vision for the project. Unsolicited pull 
requests may be ignored. For suggestions or feature requests, please open a discussion or join the Discord server.

# Social contact

If you have short or quick questions, you are free to join my [discord server](https://discord.gg/G3GpVR8xpb) and ask
the question. keep in mind it's solo project, as such it might take me a bit of time to reply.

# Donation 

If you feel like donating and appreciate my work, you can do so by donating to children charity. For example [Make-A-Wish](https://worldwish.org). 
