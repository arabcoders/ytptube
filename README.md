# YTPTube

![Build Status](https://github.com/arabcoders/ytptube/actions/workflows/main.yml/badge.svg)
![MIT License](https://img.shields.io/github/license/arabcoders/ytptube.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/arabcoders/ytptube.svg)
![GHCR Pulls](https://ghcr-badge.elias.eu.org/shield/arabcoders/ytptube/ytptube)

YTPTube is a self-hosted download manager, automation interface, and media library preparation layer for
[yt-dlp](https://github.com/yt-dlp/yt-dlp). It handles one-off downloads, recurring sources, metadata-based rules,
concurrent queues, and organized output from the same web interface.

YTPTube's automation tools can be used separately or together:

- **Tasks** check channels, playlists, feeds, and supported custom sources on a schedule.
- **Presets** store reusable yt-dlp options, output templates, paths, cookies, and post-processing settings.
- **Conditions** optionally inspect metadata returned by yt-dlp and apply matching options.

See [Features](docs/features.md) for the full workflow.

## Screenshots

Standard interface:

![Standard interface](https://raw.githubusercontent.com/ArabCoders/ytptube/dev/sc_short.jpg)

Simple mode:

![Simple mode](https://raw.githubusercontent.com/ArabCoders/ytptube/dev/sc_simple.jpg)

The interface is available in English, العربية, Français, 中文, and 日本語. See the [language FAQ](FAQ.md#how-do-i-change-the-ui-language).

## What It Handles

- Individual URLs, playlists, channels, live streams, and upcoming streams
- Concurrent downloads with global and per-extractor limits
- Scheduled Tasks for recurring sources and sites without RSS feeds
- Reusable default presets, including NFO Maker and media-server presets
- Conditions that apply yt-dlp options from extracted metadata
- Notifications for selected events through Apprise or direct HTTP webhooks
- [Firefox](https://addons.mozilla.org/en-US/firefox/addon/ytptube-extension/) and [Chrome/Chromium](https://chromewebstore.google.com/detail/ytptube-extension/kiepfnpeflemfokokgjiaelddchglfil) extensions
- [iOS Shortcuts](docs/features.md#send-links-to-ytptube), a [bookmarklet](FAQ.md#simple-bookmarklet), and an [HTTP API](API.md)
- A file browser and built-in player with external sidecar subtitle support and optional file action controls
- Kodi-style TV and movie NFO sidecars, `.info.json` metadata, artwork, and media library naming
- curl-cffi impersonation and a bundled PO-token provider
- An optional browser extraction over existing Chrome instance
- Optional direct yt-dlp control through the terminal interface
- Optional integration with FlareSolverr or Trawl to allow yt-dlp to bypass some WAF protection.
- Queue and archive controls, live logs, diagnostics, and optional resource monitoring
- Docker, Podman, Unraid, and [native builds](docs/native-builds.md) for Windows, macOS, and Linux

Read [Features](docs/features.md) for details and links to the relevant configuration guides.

## Media Libraries

YTPTube NFO Maker integration turns yt-dlp metadata into Kodi-style TV or movie `.nfo` sidecars, cleans descriptions for
library use, creates stable IDs, and keeps each NFO beside its media file. NFO files can be generated during the download
or later from history.

Scheduled Tasks can separately create collection metadata like `tvshow.nfo`, `.info.json`, and artwork images when the 
source provides them. A separate info-reader Preset writes predictable channel and season layouts with yt-dlp metadata 
for compatible Jellyfin, Emby, Plex, and WatchState workflows.

See [Media Servers and NFO Maker](docs/features.md#media-servers-and-nfo-maker) for the three workflows and their limits.

## Quick Start

The included [`compose.yaml`](compose.yaml) runs YTPTube with the bundled POT provider, Chromium browser extraction, and
FlareSolverr support. It also contains commented host-specific examples for hardware acceleration and NFS/SMB storage.
See the [environment variable reference](FAQ.md#environment-variables) for additional application settings.

Create the directories and start the container:

```bash
mkdir -p ./{config,downloads/{files,tmp}}
docker compose up -d
```

Open `http://localhost:8081` and create the first local account.

The container runs as your user and group IDs so downloaded files remain accessible to the host account. Podman users
can replace the `user` line with `userns_mode: keep-id` and run `podman-compose up -d`.

<details>
<summary>Docker command</summary>

```bash
mkdir -p ./{config,downloads/{files,tmp}} && docker run -itd --rm \
  --user "$(id -u):$(id -g)" \
  --name ytptube \
  -e YTP_TEMP_PATH=/downloads/tmp \
  -e YTP_DOWNLOAD_PATH=/downloads/files \
  -p 8081:8081 \
  -v ./config:/config:rw \
  -v ./downloads:/downloads:rw \
  ghcr.io/arabcoders/ytptube:latest
```

</details>

<details>
<summary>Podman command</summary>

```bash
mkdir -p ./{config,downloads/{files,tmp}} && podman run -itd --rm \
  --userns=keep-id \
  --name ytptube \
  -e YTP_TEMP_PATH=/downloads/tmp \
  -e YTP_DOWNLOAD_PATH=/downloads/files \
  -p 8081:8081 \
  -v ./config:/config:rw \
  -v ./downloads:/downloads:rw \
  ghcr.io/arabcoders/ytptube:latest
```

</details>

## Other Installations

### Unraid

Install the **Community Applications** plugin, search for **ytptube**, and use the pre-configured template.

### Native Builds

Download the Windows, macOS, or Linux archive from [GitHub Releases](https://github.com/arabcoders/ytptube/releases).
Read the [native-build guide](docs/native-builds.md) for installation and usage instructions.

## Security

> [!IMPORTANT]
> Do not expose YTPTube to an untrusted network without authentication. Authenticated users are instance administrators 
> and can pass yt-dlp options, including options that execute commands.

Server installations require local account setup. Only disable authentication when a trusted reverse proxy controls 
access or the instance is restricted to a private network. Read the [security recommendations](FAQ.md#security-recommendations)
before exposing an instance and use [security advisories](https://github.com/arabcoders/ytptube/security/advisories/new) 
to report vulnerabilities.

## Documentation

- [Documentation index](docs/README.md)
- [Features](docs/features.md)
- [Native builds](docs/native-builds.md)
- [Configuration, usage, and troubleshooting](FAQ.md)
- [HTTP API](API.md)
- [Security policy](SECURITY.md)
- [Contribution process](CONTRIBUTING.md)

## Project Policy

YTPTube is a personal-first project. Contributions are welcome ONLY after approval from the maintainer following prior 
discussion. Any unsolicited pull requests will be declined. Read [CONTRIBUTING.md](CONTRIBUTING.md) before starting any 
work to not waste your and the maintainer's time.

AI-assisted tools have been used in this project and will continue to be used where I find them useful. This project is
built for my own needs and use cases, and I maintain it according to my own preferences.

You are welcome to use it if it works for you, but I will not change the project's development approach to accommodate 
your objections. I believe these tools can be genuinely useful when used appropriately. If the use of AI-assisted tools 
is a deal-breaker for you, this project may not be the right fit for you. Feel free to build your own.

YTPTube is not affiliated with yt-dlp or any supported service. It is intended for downloading content you are 
permitted to access, not for piracy or unlawful use.

## Community

For short questions, join the [Discord server](https://discord.gg/G3GpVR8xpb). YTPTube is maintained as a solo project, 
so replies may take some time.

If you want to support the work financially, please donate to a children's charity such as [Make-A-Wish International](https://worldwish.org) instead.
