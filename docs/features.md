# YTPTube Features

YTPTube is a self-hosted download manager for yt-dlp. It handles manual downloads, recurring sources, metadata rules, 
reusable download settings, and media-library preparation.

## How Automation Works

1. A **Task** checks a source for new items.
2. yt-dlp extracts metadata for each item.
3. **Conditions** decide how matching items should be handled.
4. A **Preset** supplies the download settings.
5. The item enters the queue.

These parts also work independently. Presets and Conditions can be used with URLs submitted manually.

## Downloads, Queue, and History

Submit individual URLs, playlists, channels, live streams, upcoming streams, or several URLs at once. Each submission 
can use its own Preset, destination, filename template, cookies, and yt-dlp options.

The queue provides:

- Concurrent downloads with global and per-extractor limits
- Start, pause, cancel, force-start, and reorder controls
- Progress, speed, and ETA reporting
- Retry handling
- Separate temporary and destination paths
- Dedicated handling for live and upcoming streams

History keeps all processed items available for retry or inspection. Records can be removed without deleting the 
downloaded files, or removed together with their files.

Download archives stop recurring Tasks and repeated submissions from adding known items. Built-in Presets enable archive 
tracking by default, and archive entries can be managed from Tasks and History.

## Tasks

Tasks monitor sources on a schedule and add new items to the queue. Built-in handlers support:

- YouTube channels and playlists
- RSS and Atom feeds
- Twitch channel VODs
- TVer series
- Other sites through generic Task definitions

A Task can have its own Preset, folder, filename template, yt-dlp options, archive behavior, and automatic start policy. 
It can also be inspected before running to show the matched handler and discovered items.

## Monitor Sites Without RSS or APIs

Generic Task Definitions turn sites without RSS feeds, suitable APIs, or built-in handlers into recurring YTPTube
sources. They support HTML pages, JSON endpoints, and pages rendered in a remote browser. Discovered items use the same
Presets, Conditions, download archives, and queue controls as built-in Tasks.

See [Generic Task Definitions](task-definitions.md) for the schema, examples, editor workflow, and testing steps.

## Presets

Presets save settings that would otherwise need to be entered for every download:

- yt-dlp options
- Output naming
- Destination folders
- Cookies
- Priority
- Post-processing options

Built-in Presets cover normal downloads, audio-only output, mobile-compatible files, preferred 1080p and 720p output, 
NFO generation, and media-library layouts.

## Conditions

Conditions inspect yt-dlp metadata before a download starts. A matching Condition can change options, choose another
Preset, set cookies, skip an item, or bypass an archive check.

This is useful when one channel or feed contains different types of content. A Condition can be tested against a URL 
before it is enabled, and it can be ignored for an individual submission.

For example, a feed may usually release videos openly but occasionally region-lock a few items. A Condition can detect
the region lock and apply a proxy for that item or skip it entirely.

Another Condition could detect a specific keyword in the title and apply a different Preset for that item, or use cookies
for that specific item. This allows for more granular control over how different types of content are handled within the 
same feed or channel.

## Media Servers and NFO Maker

YTPTube supports three media-library workflows: NFO sidecars for individual downloads, collection metadata for recurring 
sources, and info-reader layouts for integrations that use yt-dlp metadata.

### TV and Movie NFO Files

The `nfo_maker_tv` and `nfo_maker_movie` Presets generate Kodi-style NFO files beside downloaded media. Depending on the 
mode and available metadata, an NFO can contain the title, plot, date, season and episode values, runtime, source 
identifiers, and stable IDs.

Descriptions are cleaned for library use instead of copying raw promotional links, hashtags, and chapter timestamps 
into the plot. NFO files can be created during the download or regenerated later from History without downloading 
the media again.

### Collection Metadata and Artwork

A Task can prepare the directory for a channel or recurring source. It generates `tvshow.nfo`, yt-dlp `.info.json` 
metadata, and available artwork such as posters, fanart, banners, icons, thumbnails, and landscape images.

Collection metadata describes the collection directory while the TV and movie NFO Presets describe each downloaded item 
inside it.

### Info-Reader and WatchState Workflows

The `info_reader_plugin` Preset creates predictable channel and season paths, `.info.json` files, JPEG thumbnails, and 
embedded metadata. It is intended for compatible Jellyfin, Emby, Plex, and WatchState workflows that read yt-dlp metadata.

Compatibility depends on the target media server and its installed plugin or integration. The info-reader workflow is 
separate from Kodi-style NFO generation.

## Difficult Sites

For sites that need more than a normal HTTP request, YTPTube supports browser-based extraction, HTTP impersonation, 
yt-dlp token providers, and external challenge-solving services such as FlareSolverr or Trawl.

These tools depend on the site and extractor and do not guarantee access to every protected site.
See [WAF challenge setup](../FAQ.md#how-to-bypass-some-waf-challenges) and
[browser extraction](../FAQ.md#how-to-use-the-browser-extractor).

## Files and Playback

The file browser can search, sort, preview, and download files under the configured download directory. It detects 
related subtitles and metadata sidecars. The built-in player supports compatible local media and external subtitles.

Optional file controls add directory creation, rename, move, and delete actions. They are disabled by default because 
they modify files on disk.

Browser playback and transcoding require ffmpeg. Hardware acceleration is available when supported by the host and 
container setup. See [Hardware acceleration](../FAQ.md#how-to-use-hardware-acceleration-for-video-transcoding).

## Notifications

Send notifications for selected download, queue, Task, and log events. Targets can be restricted to selected Presets 
and delivered through [Apprise](https://github.com/caronc/apprise) or direct HTTP webhooks.

## Send Links to YTPTube

- [Firefox extension](https://addons.mozilla.org/en-US/firefox/addon/ytptube-extension/)
- [Chrome and Chromium extension](https://chromewebstore.google.com/detail/ytptube-extension/kiepfnpeflemfokokgjiaelddchglfil)
- [Add To YTPTube iOS Shortcut](https://www.icloud.com/shortcuts/6df61c97d97b4e539c9100999ba39dd4)
- [YTPTube To Media iOS Shortcut](https://www.icloud.com/shortcuts/4dc579382f254635ad5785424055f173)
- [Bookmarklet](../FAQ.md#simple-bookmarklet)
- [HTTP API](../API.md)

The **Add To YTPTube** Shortcut sends a page to your instance and lets you choose a Preset. **YTPTube To Media** attempts 
to download media directly to the iOS device. The latter is provided without support and does not fully handle HTTP headers.

## Security Boundary

YTPTube is an administrative interface around yt-dlp, not a multi-user sandbox. Authenticated users can control downloads
and supply yt-dlp options, including options that execute commands.

Keep authentication enabled on untrusted networks and limit container mounts and permissions to what YTPTube needs. 
Read the [security recommendations](../FAQ.md#security-recommendations) before exposing an instance.

## More Documentation

- [README](../README.md): installation and project overview
- [Native builds](native-builds.md): Windows, macOS, and Linux installation and operation
- [FAQ](../FAQ.md): configuration, integrations, and troubleshooting
- [API](../API.md): programmatic access
- [Security policy](../SECURITY.md): vulnerability reporting and supported boundaries
