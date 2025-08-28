# HTTP API Documentation

This document describes the available endpoints and their usage. All endpoints return JSON responses (unless otherwise specified) and may require certain parameters (query, body, or path). Some endpoints serve static or streaming content (e.g., `.ts`, `.m3u8`, `.vtt` files).

> **Note**: If Basic Authentication is configured (via `auth_username` and `auth_password` in your configuration), you must include an `Authorization: Basic <urlsafe-base64-encoded-credentials>` header or use `?apikey=<urlsafe-base64-encoded-credentials>` query parameter (fallback) in every request.

- All responses use standard HTTP status codes to indicate success or error conditions.
- Endpoints support an `OPTIONS` request for CORS.

---

## Table of Contents

- [HTTP API Documentation](#http-api-documentation)
  - [Table of Contents](#table-of-contents)
  - [Authentication](#authentication)
  - [Global Notes](#global-notes)
  - [Endpoints](#endpoints)
    - [GET /api/ping](#get-apiping)
    - [POST /api/yt-dlp/convert](#post-apiyt-dlpconvert)
    - [GET /api/yt-dlp/url/info](#get-apiyt-dlpurlinfo)
    - [GET /api/history/add](#get-apihistoryadd)
    - [POST /api/history](#post-apihistory)
    - [DELETE /api/history](#delete-apihistory)
    - [POST /api/history/{id}](#post-apihistoryid)
    - [GET /api/history/{id}](#get-apihistoryid)
    - [GET /api/history](#get-apihistory)
    - [DELETE /api/archive/{id}](#delete-apiarchiveid)
    - [POST /api/archive/{id}](#post-apiarchiveid)
    - [GET /api/tasks](#get-apitasks)
    - [PUT /api/tasks](#put-apitasks)
    - [POST /api/tasks/{id}/mark](#post-apitasksidmark)
    - [GET /api/player/playlist/{file:.\*}.m3u8](#get-apiplayerplaylistfilem3u8)
    - [GET /api/player/m3u8/{mode}/{file:.\*}.m3u8](#get-apiplayerm3u8modefilem3u8)
    - [GET /api/player/segments/{segment}/{file:.\*}.ts](#get-apiplayersegmentssegmentfilets)
    - [GET /api/player/subtitle/{file:.\*}.vtt](#get-apiplayersubtitlefilevtt)
    - [GET /api/thumbnail](#get-apithumbnail)
    - [GET /api/file/ffprobe/{file:.\*}](#get-apifileffprobefile)
    - [GET /api/file/info/{file:.\*}](#get-apifileinfofile)
    - [GET /api/file/browser/{path:.\*}](#get-apifilebrowserpath)
    - [POST /api/file/action/{path:.\*}](#post-apifileactionpath)
    - [POST /api/file/download](#post-apifiledownload)
    - [GET /api/file/download/{token}](#get-apifiledownloadtoken)
    - [GET /api/random/background](#get-apirandombackground)
    - [GET /api/presets](#get-apipresets)
    - [GET /api/dl\_fields](#get-apidl_fields)
    - [PUT /api/dl\_fields](#put-apidl_fields)
    - [PUT /api/presets](#put-apipresets)
    - [GET /api/conditions](#get-apiconditions)
    - [PUT /api/conditions](#put-apiconditions)
    - [POST /api/conditions/test](#post-apiconditionstest)
    - [GET /api/logs](#get-apilogs)
    - [GET /api/notifications](#get-apinotifications)
    - [PUT /api/notifications](#put-apinotifications)
    - [POST /api/yt-dlp/archive\_id/](#post-apiyt-dlparchive_id)
    - [POST /api/notifications/test](#post-apinotificationstest)
    - [GET /api/yt-dlp/options](#get-apiyt-dlpoptions)
    - [POST /api/system/shutdown](#post-apisystemshutdown)
    - [GET /api/dev/loop](#get-apidevloop)
    - [GET /api/dev/pip](#get-apidevpip)
  - [Error Responses](#error-responses)

---

## Authentication

If `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` are set, all API requests must include a valid credential using one of the following:

1. HTTP Basic Auth header:

   ```
   Authorization: Basic base64("<username>:<password>")
   ```

2. Query Parameter fallback:

   ```
   ?apikey=<base64_urlsafe("<username>:<password>")>
   ```

If you fail to provide valid credentials, a `401 Unauthorized` response is returned.

---

## Global Notes

- **Content-Type**  
  - Requests expecting a JSON body should include `Content-Type: application/json`.  
  - Responses typically include `Content-Type: application/json`, unless returning a file or streaming resource.

- **Status Codes**  
  - `200 OK` on success.  
  - `4xx` on client errors (e.g., missing parameters).  
  - `5xx` on server errors (e.g., unexpected failures).

- **Error Responses**  
  When an error occurs, responses follow a structure similar to:
  ```json
  {
    "error": "Description of the error",
  }
  ```
  with an appropriate HTTP status code.

---

## Endpoints

### GET /api/ping
**Purpose**: Health-check endpoint.  
**Response**:
```json
{
  "status": "pong"
}
```

---

### POST /api/yt-dlp/convert
**Purpose**: Convert a string of yt-dlp options into a JSON-friendly structure.

**Body**:
```json
{
  "args": "<string>"
}
```
**Example**:
```json
{
  "args": "--write-sub --embed-subs"
}
```
**Response**:  
```json
{
    "opts": { ... },
    "output_template": "...",
    "download_path": "...",
    "removed_options": ["option1", "option2"]  // optional, only if options were removed
}
```
or an error:
```json
{
  "error": "Failed to parse command options for yt-dlp. '<reason>'."
}
```

---

### GET /api/yt-dlp/url/info
**Purpose**: Retrieves metadata (info) for a provided URL without adding it to the download queue.

**Query Parameters**:
- `url=<video-url>` (required)
- `preset=<preset-name>` (optional) - The preset to use for extracting info.
- `force=true` (optional) - Force fetch new info instead of using cache.
- `args=<yt-dlp-command-opts>` (optional) - The yt-dlp command options to apply to the info extraction.

**Response** (example):
```json
{
  "title": "...",
  "duration": 123.4,
  "extractor": "youtube",
  "_cached": {
    "status": "miss|hit",
    "preset": "<preset-name>",
    "cli_args": "<yt-dlp-command-opts>",
    "key": "<hash>",
    "ttl": 300,
    "ttl_left": 299.82,
    "expires": 1690430096.429
  },
  ...
}
```
or an error:
```json
{
  "error": "text"
}
```
- If the URL is invalid or missing, returns `400 Bad Request`.
- If the preset is specified and not found, returns `404 Not Found`.

---

### GET /api/history/add
**Purpose**: **(Quick Add)** Add a single URL to the download queue via GET.  

**Query Parameters**:
- `url=<video-url>`
- `preset=<preset-name>`

**Response**:
```json
{
  "status": true|false, # true if added to the queue. false otherwise.
  "message": "..." # the response message.
}
```

- If `url` is missing, returns `400 Bad Request`.
- If `preset` is set and not found, returns `404 Not Found`.

> [!NOTE]
> This endpoint is a quick way to add a single item to the queue without needing to format a full JSON body. It is primarily for convenience and may not support all options available in the full POST `/api/history` endpoint.
> Also note, that the endpoint uses different error format compared to the other endpoints, returning a simple JSON object with `status` and `message` fields.
> This is to make easier to script bookmarklets or simple API requests.

---

### POST /api/history
**Purpose**: Add one or multiple items (URLs) to the download queue via JSON body.  

**Body**:
```json5
// Single item
{
  "url": "https://youtube.com/watch?v=...", // -- required. The video URL to download.
  "preset": "default", // -- optional. The preset to use for this item.
  "folder": "my_channel/foo", // -- optional. The folder to save the item in, relative to the `download_path`.
  "cookies": "...", // -- optional. If provided, it MUST BE in Netscape HTTP Cookie format.
  "template": "%(title)s.%(ext)s", // -- optional. The filename template to use for this item.
  "cli": "--write-subs --embed-subs", // -- optional. Additional command options for yt-dlp to apply to this item.
  "auto_start": true // -- optional. Whether to auto-start the download after adding it. Defaults to true.
}

// Or multiple items (array of objects)
[
  {
    "url": "...",
    "preset": "default",
    ...
  },
  {
    "url": "...",
    ...
  }
]
```
**Response**:
```json
[
  {
    "status": "queued",
  },
  ...
]
```
- If any item is invalid (e.g., missing `url`), returns `400 Bad Request`.

---

### DELETE /api/history
**Purpose**: Delete items from either the "queue" or the "done" history.  

**Body**:
```json
{
  "ids": ["<id1>", "<id2>"],
  "where": "queue" | "done",
  "remove_file": true | false   // optional, defaults to True, whether to delete the file from disk if enabled.
}
```
**Response**:  

```json
{
  "<id1>": "status",
  "<id2>": "status",
  ...
}
```

A list or object indicating which items were removed.

---

### POST /api/history/{id}
**Purpose**: Update an item in the `completed` history.

**Path Parameter**:
- `id` = Unique item ID.

**Body** (example):
```json
{
  "title": "My Custom Title",
  "someOtherField": "new-value"
}
```
**Response**:
```json
{
  "title": "My Custom Title",
  ....
}
```
or an error:
```json
{
  "error": "text"
}
```

- `200 OK` with updated item if successful.
- `304 Not Modified` if nothing changed.
- `404 Not Found` if the item doesn’t exist.
- `400 Bad Request` if id is missing or the body is empty.

---

### GET /api/history/{id}
**Purpose**: View details of a specific item in the database.

**Path Parameter**:
- `id` = Unique item ID.

**Response**:
```json
{
  "_id": "<uuid>",
  "title": "Video Title",
  "url": "https://youtube.com/watch?v=...",
  ....
}
```
or an error:
```json
{
  "error": "text"
}
```

- `200 OK` If the item exists and is returned.
- `404 Not Found` if the item doesn’t exist.
- `400 Bad Request` if id is missing.

---

### GET /api/history
**Purpose**: Returns the download queue and the download history.  

**Response**:
```json
{
  "queue": [
    { ... },
    ...
  ],
  "history": [
    { ... },
    ...
  ]
}
```

---

### DELETE /api/archive/{id}
**Purpose**: Remove an item's URL from the yt-dlp archive file, allowing it to be re-downloaded.

**Path Parameter**:
- `id`: Item ID from the history (if body `url` is not provided).

**Body (optional)**:
```json
{ "url": "https://..." }
```
If `url` is provided, it is used directly; otherwise the route resolves the item by `id` and uses its URL.

**Response**:
```json
{ "message": "item '<title>' removed from '<archive_file>' archive." }
```
or an error:
```json
{ "error": "text" }
```

- `400 Bad Request` if archive is not configured or parameters are invalid.
- `404 Not Found` if the item or archive entry is not found.

---

### POST /api/archive/{id}
**Purpose**: Manually mark an item as archived by writing its archive ID to the archive file.

**Path Parameter**:
- `id`: Item ID from the history.

**Response**:
```json
{ "message": "item '<archive_id>' archived in file '<archive_file>'." }
```
or an error:
```json
{ "error": "text" }
```

- `404 Not Found` if the item or archive file does not exist.
- `409 Conflict` if the item is already archived.

---

### GET /api/tasks
**Purpose**: Retrieves the scheduled tasks from the internal `Tasks` manager.  

**Response**:
```json
[
  {
    "id": "<uuid>",
    "name": "...",
    "url": "...",
    "folder": "...",
    "preset": "...",
    "timer": "<cron-expression>",
    "template": "...",
    "cookies": "...",
    "config": { ... },
  },
  ...
]
```

---

### PUT /api/tasks
**Purpose**: Overwrites the entire scheduled tasks list (Cron tasks).  

**Body**: An array of task objects. Example:
```json
[
  {
    "id": "a2ae3f18-4428-4e32-9d4c-0cc45af8bb48",
    "name": "My Task",
    "url": "https://youtube.com/...",
    "timer": "5 */2 * * *",
    "cookies": "",
    "config": {},
    "template": "...",
    "folder": "..."
  },
  {
    "url": "https://youtube.com/...",
    "timer": "*/15 * * * *"
  }
]
```
If `id` or other fields are missing, they may be auto-generated or defaulted (e.g., a random ID, a default cron, etc.).

**Response**:
```json
[
  {
    "id": "<uuid>",
    "name": "...",
    "url": "...",
    "timer": "...",
    "cookies": "...",
    "config": { ... },
    "template": "...",
    "folder": "..."
  }
  ...
]
```
or on error
```json
{
  "error": "text"
}
```

---

### POST /api/tasks/{id}/mark
**Purpose**: Mark all entries associated with a scheduled task as downloaded.

**Path Parameter**:
- `id`: Task ID.

**Response**:
```json
{ "message": "..." }
```
or
```json
{ "error": "..." }
```

- `400 Bad Request` if id is missing or invalid.
- `404 Not Found` if the task does not exist.

---

### GET /api/player/playlist/{file:.*}.m3u8
**Purpose**: Generate a playlist for a given local media file.

**Path Parameter**:
- `file` = Relative path of the media file within the `download_path`.

**Response**:  
An `.m3u8` playlist.

---

### GET /api/player/m3u8/{mode}/{file:.*}.m3u8
**Purpose**: Dynamically generate an M3U8 playlist for video or subtitles.  

**Path Parameters**:
- `mode`: either `video` or `subtitle`.
- `file`: relative path of the file.

**Query Parameters (when `mode=subtitle`)**:
- `duration`: The total duration of the subtitle track

**Response**:
- `Content-Type: application/x-mpegURL` containing the `.m3u8` text.

---

### GET /api/player/segments/{segment}/{file:.*}.ts
**Purpose**: Streams a single TS segment for adaptive HLS playback.  

**Path Parameters**:
- `segment` = Numeric segment index.
- `file` = Relative file path.

**Query Parameters**:
- `sd` = The segment duration (float).  
- `vc` = `1` or `0` (whether to convert video).  
- `ac` = `1` or `0` (whether to convert audio).

**Response**:  
Binary TS data (`Content-Type: video/mpegts`).

---

### GET /api/player/subtitle/{file:.*}.vtt
**Purpose**: Provides a `.vtt` (WebVTT) subtitle file for playback.  

**Path Parameter**:
- `file` = Relative path of the subtitle file.

**Response**:  
`Content-Type: text/vtt; charset=UTF-8`.

---

### GET /api/thumbnail
**Purpose**: Proxy/fetch a remote thumbnail image.  

**Query Parameter**:
- `?url=<remote-thumbnail-url>`

**Response**:  
Binary image data with the appropriate `Content-Type`.

---

### GET /api/file/ffprobe/{file:.*}
**Purpose**: Return the `ffprobe` data for a local file.  

**Path Parameter**:
- `file` = Relative path to the file inside `download_path`.

**Response**:
```json
{
  "streams": [...],
  "format": { ... },
  ...
}
```

### GET /api/file/info/{file:.*}
**Purpose**: Get comprehensive file information including ffprobe data, MIME type, and sidecar files.  

**Path Parameter**:
- `file` = Relative path to the file inside `download_path`.

**Response**:
```json
{
  "title": "filename",
  "ffprobe": {
    "streams": [...],
    "format": { ... },
    ...
  },
  "mimetype": "video/mp4",
  "sidecar": {
    "subtitles": [
      {
        "file": "filename.xxx.vtt",
        "lang": "xxx",
        "name": "VTT 0 - XXX|end",
      },
      ...
      }
    ],
    "video": [],
    "audio": [],
    "image": [],
    "text": [],
    "metadata": [],
    ...
  }
}
```

---

### GET /api/file/browser/{path:.*}
**Purpose**: Browse files and directories within the download path (if browser is enabled).  

**Path Parameter**:
- `path` = Relative path within the download directory (URL-encoded).

**Response**:
```json
{
  "path": "/some/path",
  "contents": [
    {
      "type": "file",
      "content_type": "video|subtitle|audio|image|text|metadata|dir|download",
      "name": "filename.mp4",
      "path": "/filename.mp4",
      "size": 123456789,
      "mimetype": "mime/type",
      "mtime": "2023-01-01T12:00:00Z",
      "ctime": "2023-01-01T12:00:00Z",
      "is_dir": true|false,
      "is_file": true|false,
      ...
    },
    {
      "type": "dir",
      "content_type": "dir",
      "name": "Season 2025",
      "path": "/Season 2025",
      ...
    }
  ]
}
```
- Returns `403 Forbidden` if file browser is disabled.
- Returns `404 Not Found` if the path doesn't exist.

---

### POST /api/file/action/{path:.*}
**Purpose**: Perform a file browser action on a file or directory.

**Path Parameter**:
- `path`: Base path (relative to `download_path`) to operate under. Use `/` for root.

**Body**:
```json
{ "action": "rename|delete|move|directory", ... }
```
Actions and required fields:
- `rename`: `{ "new_name": "<name>" }`
- `delete`: no extra fields
- `move`: `{ "new_path": "<dir-relative-to-download_path>" }`
- `directory`: `{ "new_dir": "<subdir/to/create>" }`

**Response**: `200 OK` with empty body.

or an error:
```json
{ "error": "text" }
```

- `403 Forbidden` if browser or actions are disabled.
- `400/404` for invalid paths or parameters.

---

### POST /api/file/download
**Purpose**: Prepare a ZIP download of selected files (and detected sidecars). Returns a short-lived token.

**Body**:
```json
[ "relative/path/file1.ext", "relative/path/file2.ext" ]
```

**Response**:
```json
{ "token": "<uuid>", "files": ["relative/path/file1.ext", "..."] }
```

- `400 Bad Request` if the body is not a JSON array or contains no valid files.

---

### GET /api/file/download/{token}
**Purpose**: Stream a ZIP file for the previously prepared download token.

**Path Parameter**:
- `token`: Token returned by POST `/api/file/download`.

**Response**:
- `200 OK` streaming response with `Content-Type: application/zip` and `Content-Disposition: attachment`.
- JSON error with `400 Bad Request` if the token is invalid/expired or no files available.

---

### GET /api/random/background
**Purpose**: Get a random background image from configured backends.  

**Query Parameters**:
- `force=true` (optional) - Force fetch a new image instead of using cache.

**Response**:
Binary image data with appropriate `Content-Type` header.

---

### GET /api/presets
**Purpose**: Retrieve all available download presets.  

**Query Parameters**:
- `filter=<field1,field2>` (optional) - Comma-separated list of fields to include in response.

**Response**:
```json5
[
  {
    "id": "<uuid>",
    "name": "preset_name",
    "description": "...",
    "folder": "my_channel/foo",
    "template": "%(title)s.%(ext)s",
    "cookies": "...",
    "cli": "--write-subs --embed-subs",
    "default": true|false, // optional, indicates if this is the default preset.
    ...
  },
  ...
]
```

---

### GET /api/dl_fields
**Purpose**: Retrieve the list of configured download fields.

**Query Parameters (optional)**:
- `filter`: Comma-separated list of field names to include in each object.

**Response**:
```json
[
  { "id": "<uuid>", "name": "...", ... },
  ...
]
```

---

### PUT /api/dl_fields
**Purpose**: Save the list of download fields. Replaces existing entries.

**Body**: Array of objects. Required per-item fields: `name`. `id` is auto-generated if missing or invalid.
```json
[
  { "name": "...", "id": "<uuid>", ... },
  { "name": "..." }
]
```

**Response**:
```json
[
  { "id": "<uuid>", "name": "...", ... },
  ...
]
```
or an error:
```json
{ "error": "text" }
```

---

### PUT /api/presets
**Purpose**: Save/update download presets.  

**Body**: An array of preset objects:
```json
[
  {
    "name": "My Preset", // required, unique name for the preset
    "id": "<uuid>",  // optional, will be generated if not provided
    "description": "...", // optional, description of the preset
    "folder": "my_channel/foo", // optional, relative to download_path
    "template": "%(title)s.%(ext)s", // optional, filename template
    "cookies": "...", // optional, Netscape HTTP Cookie format
    "cli": "--write-subs --embed-subs", // optional, additional command options for yt-dlp
  },
  ...
]
```

**Response**:
```json
[
  {
    "id": "<uuid>",
    "name": "My Preset",
    "description": "...",
  },
  ...
]
```

---

### GET /api/conditions
**Purpose**: Retrieve all configured download conditions.  

**Response**:
```json
[
  {
    "id": "<uuid>",
    "name": "condition_name",
    "filter": "...",
    "cli": "...",
    ...
  },
  ...
]
```

---

### PUT /api/conditions
**Purpose**: Save/update download conditions.  

**Body**: An array of condition objects:
```json
[
  {
    "id": "<uuid>",  // optional, will be generated if not provided
    "name": "Use proxy for region locked content",
    "filter": "availability = 'needs_auth' & channel_id = 'channel_id'",
    "cli": "--proxy http://myproxy.com:8080",
  },
  ...
]
```

**Response**:
```json
[
  {
    "id": "<uuid>",
    "name": "Use proxy for region locked content",
    "filter": "availability = 'needs_auth' & channel_id = 'channel_id'",
    "cli": "--proxy http://myproxy.com:8080",
  },
  ...
]
```

---

### POST /api/conditions/test
**Purpose**: Evaluate a condition expression against info extracted from a URL.

**Body**:
```json
{ "url": "https://...", "condition": "yt:duration > 600", "preset": "<optional-preset>" }
```

**Response**:
```json
{
  "status": true,
  "condition": "...",
  "data": { ... }  // sanitized, possibly large
}
```

- `400 Bad Request` for invalid body, missing fields, or extractor failures.

---

### GET /api/logs
**Purpose**: Retrieve recent application logs (if file logging is enabled).  

**Query Parameters**:
- `offset=<number>` (optional, default: 0) - Number of log entries to skip.
- `limit=<number>` (optional, default: 100, max: 150) - Number of log entries to return.

**Response**:
```json
{
  "logs": [
    {
      "timestamp": "2023-01-01T12:00:00Z",
      "level": "INFO",
      "message": "...",
      ...
    },
    ...
  ],
  "offset": 0,
  "limit": 100,
  "next_offset": 100,
  "end_is_reached": false
}
```
- Returns `404 Not Found` if file logging is not enabled.

---

### GET /api/notifications
**Purpose**: Retrieve the configured notification targets and which event types are allowed.  

**Response** (example):
```json
{
  "notifications": [
    {
      "id": "uuid",
      "name":"...",
      "on": ["completed", "error",...], // empty array means all events.
      "request":{
        "type":"json|form",
        "method":"POST|PUT",
        "url":"https://...",
        "headers":[
          {"key":"...", "value":"..."},
          ...
        ]
        }
      }
    }
  ],
  "allowedTypes": ["added", "completed", "error", "cancelled", "cleared", "log_info", "log_success", "log_warning", "log_error", "test"]
}
```

---

### PUT /api/notifications
**Purpose**: Overwrites the entire list of notification targets.  

**Body**: An array of notification target configurations. Example:
```json
[
  {
    "id": "uuid",
    "name": "My Webhook",
    "on": ["completed", "error"],
    "request": {
      "type": "json",
      "method": "POST",
      "url": "https://...",
      "headers": [
        { "key": "Authorization", "value": "Bearer ..." }
      ]
    }
  },
  {
    "name": "Another Webhook",
    "on": ["completed"],
    "request": {
      "type": "form",
      "method": "PUT",
      "url": "https://...",
      "headers": []
    }
  }
  ...
]
```
- If `id` is not provided or is not a valid UUIDv4, it will be auto-generated.
- If the payload list is empty, all existing notifications are removed.

**Response**:
```json
{
  "notifications": [
    {
      "id": "uuid",
      "name": "...",
      "on": ["completed", "error", ...],
      "request": { ... }
    },
    ...
  ],
  "allowedTypes": ["added", "completed", "error", "cancelled", "cleared", "log_info", "log_success", ...]
}
```
---

### POST /api/yt-dlp/archive_id/
**Purpose**: Get the archive ID for a given URLs.
**Body**: Array of URLs.
```json
[
    "https://youtube.com/...",
    "https://..."
}
```

**Response**:
```json
[
  {
    "index": "index_of_the_url_in_request_array",
    "url": "the_url",
    "id": "the_video_id_or_null_if_not_found",
    "ie_key": "the_extractor_key_or_null_if_not_found",
    "archive_id": "the_archive_id_or_null_if_not_found",
    "error": "error_message_if_any_or_null"
  },
  ...
]
```

or an error:
```json
{
  "error": "text"
}
```

- If the body is not a valid JSON array, returns `400 Bad Request`.

---

### POST /api/notifications/test
**Purpose**: Triggers a test notification event to all configured targets.  

**Response**:
```json
{
  "type": "test",
  "message": "This is a test notification."
}
```

---

### GET /api/yt-dlp/options
**Purpose**: Get the current yt-dlp CLI options as a JSON object.

**Response**:
```json
[
  {
    "description": "Description of the option",
    "flags":[ "--option", "-o" ],
    "group": "Option Group",
    "ignored": false, // true if this option is ignored by ytptube.
  },
  ...
]
```

---

### POST /api/system/shutdown
**Purpose**: Gracefully shut down the application (native mode only).

**Response**:
```json
{ "message": "The application shutting down." }
```

- `400 Bad Request` if not running in native mode.

---

### GET /api/dev/loop
**Purpose**: Development-only. Show event loop details and running tasks.

**Response**:
```json
{ "total_tasks": 1, "loop": "...", "tasks": [ { "task": "...", "stack": ["..."] } ] }
```

- `403 Forbidden` if not in development mode.

---

### GET /api/dev/pip
**Purpose**: Development-only. Return installed versions for configured pip packages.

**Response**:
```json
{ "package": "version-or-null", "...": null }
```

---

## Error Responses

Most endpoints return standard error codes (`400`, `403`, `404`, `500`, etc.) and a JSON body on failure. For example:
```json
{
  "error": "url param is required."
}
```
with `400 Bad Request`, or:
```json
{
  "error": "Item not found."
}
```
with `404 Not Found`.

---
