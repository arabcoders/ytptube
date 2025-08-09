# I cant download anything

If you are receiving errors like:
- "OSError: [Errno 5] I/O error"
- "OSError: [Errno 18] Cross-device link: '/tmp/random_id/name.webm' -> '/downloads/name.webm'
- "Operation not permitted: '/downloads/name.webm'

This indicates an error with your mounts and how they interact with the container. So, the basic solution is to do the following:

```yaml
services:
  ytptube:
    user: "${UID:-1000}:${UID:-1000}" # change this to your user id and group id, for example: "1000:1000"
    image: ghcr.io/arabcoders/ytptube:latest
    container_name: ytptube
    restart: unless-stopped
    environment:
      - YTP_TEMP_PATH=/downloads/tmp
      - YTP_DOWNLOAD_PATH=/downloads/files
    ports:
      - "8081:8081"
    volumes:
      - ./config:/config:rw
      - ./downloads:/downloads:rw
```

Then run the following command to create the necessary directories and start the container:

```bash
mkdir -p ./config && mkdir -p ./downloads/{tmp,files} && docker compose -f compose.yaml up -d
```

Reference: [Issue #363](https://github.com/arabcoders/ytptube/issues/363)

# I want to use link with playlist but only download the video not all the videos in the playlist?

Simply create a preset, and in the `Command options for yt-dlp` field set `--no-playlist`. Then select the preset 
whenever the link includes a playlist id.

> [!NOTE]
> You can also do the same via advanced options `Command options for yt-dlp` field, but presets are more convenient.

# Install specific yt-dlp version?

You can force specific version of `yt-dlp` by setting the `YTP_YTDLP_VERSION` environment variable for example

```env
YTP_YTDLP_VERSION=2025.07.21 or master or nightly

Then restart the container to apply the changes.

