# HTTP API Documentation

This document describes the available endpoints and their usage. All endpoints return JSON responses (unless otherwise specified) and may require certain parameters (query, body, or path). Some endpoints serve static or streaming content (e.g., `.ts`, `.m3u8`, `.vtt` files).

> **Note**: If Basic Authentication is configured, you must include an `Authorization: Basic <urlsafe-base64-encoded-credentials>` header or use `?apikey=<urlsafe-base64-encoded-credentials>` query parameter (fallback) in every request.

- All responses use standard HTTP status codes to indicate success or error conditions.

---

## Table of Contents

- [HTTP API Documentation](#http-api-documentation)
  - [Table of Contents](#table-of-contents)
  - [Authentication](#authentication)
  - [Global Notes](#global-notes)
  - [Endpoints](#endpoints)
    - [GET /api/ping](#get-apiping)
    - [POST /api/yt-dlp/convert](#post-apiyt-dlpconvert)
    - [POST /api/yt-dlp/command/](#post-apiyt-dlpcommand)
    - [GET /api/yt-dlp/url/info](#get-apiyt-dlpurlinfo)
    - [GET /api/history/add](#get-apihistoryadd)
    - [POST /api/history](#post-apihistory)
    - [DELETE /api/history](#delete-apihistory)
    - [POST /api/history/{id}](#post-apihistoryid)
    - [GET /api/history/{id}](#get-apihistoryid)
    - [GET /api/history](#get-apihistory)
    - [GET /api/history/live](#get-apihistorylive)
    - [POST /api/history/start](#post-apihistorystart)
    - [POST /api/history/pause](#post-apihistorypause)
    - [POST /api/history/cancel](#post-apihistorycancel)
    - [DELETE /api/history/{id}/archive](#delete-apihistoryidarchive)
    - [POST /api/history/{id}/archive](#post-apihistoryidarchive)
    - [GET /api/archiver](#get-apiarchiver)
    - [POST /api/archiver](#post-apiarchiver)
    - [DELETE /api/archiver](#delete-apiarchiver)
    - [GET /api/tasks](#get-apitasks)
    - [POST /api/tasks](#post-apitasks)
    - [GET /api/tasks/{id}](#get-apitasksid)
    - [DELETE /api/tasks/{id}](#delete-apitasksid)
    - [PATCH /api/tasks/{id}](#patch-apitasksid)
    - [PUT /api/tasks/{id}](#put-apitasksid)
    - [POST /api/tasks/inspect](#post-apitasksinspect)
    - [POST /api/tasks/{id}/mark](#post-apitasksidmark)
    - [DELETE /api/tasks/{id}/mark](#delete-apitasksidmark)
    - [POST /api/tasks/{id}/metadata](#post-apitasksidmetadata)
    - [GET /api/tasks/definitions/](#get-apitasksdefinitions)
    - [GET /api/tasks/definitions/{id}](#get-apitasksdefinitionsid)
    - [POST /api/tasks/definitions/](#post-apitasksdefinitions)
    - [PUT /api/tasks/definitions/{id}](#put-apitasksdefinitionsid)
    - [PATCH /api/tasks/definitions/{id}](#patch-apitasksdefinitionsid)
    - [DELETE /api/tasks/definitions/{id}](#delete-apitasksdefinitionsid)
    - [GET /api/player/playlist/{file:.\*}.m3u8](#get-apiplayerplaylistfilem3u8)
    - [GET /api/player/m3u8/{mode}/{file:.\*}.m3u8](#get-apiplayerm3u8modefilem3u8)
    - [GET /api/player/segments/{segment}/{file:.\*}.ts](#get-apiplayersegmentssegmentfilets)
    - [GET /api/player/subtitle/{file:.\*}.vtt](#get-apiplayersubtitlefilevtt)
    - [GET /api/thumbnail](#get-apithumbnail)
    - [GET /api/file/ffprobe/{file:.\*}](#get-apifileffprobefile)
    - [GET /api/file/info/{file:.\*}](#get-apifileinfofile)
    - [GET /api/file/browser/{path:.\*}](#get-apifilebrowserpath)
    - [POST /api/file/actions](#post-apifileactions)
    - [POST /api/file/download](#post-apifiledownload)
    - [GET /api/file/download/{token}](#get-apifiledownloadtoken)
    - [GET /api/download/{filename}](#get-apidownloadfilename)
    - [GET /api/random/background](#get-apirandombackground)
    - [GET /api/presets](#get-apipresets)
    - [GET /api/presets/{id}](#get-apipresetsid)
    - [POST /api/presets](#post-apipresets)
    - [PATCH /api/presets/{id}](#patch-apipresetsid)
    - [PUT /api/presets/{id}](#put-apipresetsid)
    - [DELETE /api/presets/{id}](#delete-apipresetsid)
    - [GET /api/dl\_fields/](#get-apidl_fields)
    - [POST /api/dl\_fields/](#post-apidl_fields)
    - [GET /api/dl\_fields/{id}](#get-apidl_fieldsid)
    - [PATCH /api/dl\_fields/{id}](#patch-apidl_fieldsid)
    - [PUT /api/dl\_fields/{id}](#put-apidl_fieldsid)
    - [DELETE /api/dl\_fields/{id}](#delete-apidl_fieldsid)
    - [GET /api/conditions/](#get-apiconditions)
    - [POST /api/conditions/](#post-apiconditions)
    - [POST /api/conditions/test](#post-apiconditionstest)
    - [GET /api/conditions/{id}](#get-apiconditionsid)
    - [PATCH /api/conditions/{id}](#patch-apiconditionsid)
    - [PUT /api/conditions/{id}](#put-apiconditionsid)
    - [DELETE /api/conditions/{id}](#delete-apiconditionsid)
    - [GET /api/logs](#get-apilogs)
    - [GET /api/logs/stream](#get-apilogsstream)
    - [GET /api/notifications/](#get-apinotifications)
    - [GET /api/notifications/events/](#get-apinotificationsevents)
    - [POST /api/notifications/](#post-apinotifications)
    - [GET /api/notifications/{id}](#get-apinotificationsid)
    - [PATCH /api/notifications/{id}](#patch-apinotificationsid)
    - [PUT /api/notifications/{id}](#put-apinotificationsid)
    - [DELETE /api/notifications/{id}](#delete-apinotificationsid)
    - [POST /api/yt-dlp/archive\_id/](#post-apiyt-dlparchive_id)
    - [POST /api/notifications/test](#post-apinotificationstest)
    - [GET /api/yt-dlp/options](#get-apiyt-dlpoptions)
    - [GET /api/system/configuration](#get-apisystemconfiguration)
    - [POST /api/system/terminal](#post-apisystemterminal)
    - [POST /api/system/pause](#post-apisystempause)
    - [POST /api/system/resume](#post-apisystemresume)
    - [POST /api/system/shutdown](#post-apisystemshutdown)
    - [POST /api/system/check-updates](#post-apisystemcheck-updates)
    - [GET /api/dev/loop](#get-apidevloop)
    - [GET /api/dev/pip](#get-apidevpip)
    - [GET /api/docs/{file}](#get-apidocsfile)
  - [WebSocket API](#websocket-api)
    - [Connection](#connection)
    - [Authentication](#authentication-1)
    - [Message Format](#message-format)
    - [Client Events (Client → Server)](#client-events-client--server)
      - [`add_url`](#add_url)
      - [`item_cancel`](#item_cancel)
      - [`item_delete`](#item_delete)
      - [`item_start`](#item_start)
      - [`item_pause`](#item_pause)
    - [Server Events (Server → Client)](#server-events-server--client)
      - [Connection Events](#connection-events)
        - [`config_update`](#config_update)
        - [`connected`](#connected)
        - [`active_queue`](#active_queue)
      - [Logging Events](#logging-events)
        - [`log_info`](#log_info)
        - [`log_success`](#log_success)
        - [`log_warning`](#log_warning)
        - [`log_error`](#log_error)
      - [Download Queue Events](#download-queue-events)
        - [`item_added`](#item_added)
        - [`item_updated`](#item_updated)
        - [`item_cancelled`](#item_cancelled)
        - [`item_deleted`](#item_deleted)
        - [`item_moved`](#item_moved)
        - [`item_status`](#item_status)
        - [`paused`](#paused)
        - [`resumed`](#resumed)
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

**Notes**:
- IDs are integer values generated by the database.

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

### POST /api/yt-dlp/command/
**Purpose**: Build a complete yt-dlp CLI command string with priority-based argument merging from user input, presets, and defaults.

**Requires**: Console must be enabled (`YTP_CONSOLE_ENABLED=true` env).

**Body**: JSON object:
```json
{
  "url": "https://example.com/video",// required - item url
  "preset": "preset_name",           // optional - preset name to apply
  "folder": "subfolder",             // optional - output folder (relative to download_path)
  "template": "%(title)s.%(ext)s",   // optional - output filename template
  "cli": "--write-sub --embed-subs", // optional - additional yt-dlp CLI arguments
  "cookies": "cookie_string"         // optional - authentication cookies as string
}
```

If cookies are given, they will be stored in a temporary file and the appropriate `--cookies <file>` argument 
will be added to the command.

**Priority System** (User > Preset > Default):
1. **User fields** take highest priority (from request body)
2. **Preset fields** used only if user didn't provide them
3. **Default fields** used as final fallback (from configuration)

**Response**:
```json
{
  "command": "--output-path /downloads/subfolder --output %(title)s.%(ext)s --write-sub --embed-subs https://example.com/video"
}
```

**Error Responses**:
- `403 Forbidden` if console is disabled
- `400 Bad Request` if body is invalid JSON or Item format validation fails
- `400 Bad Request` if CLI command building fails

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

**Body Parameters**:
- `type` (string, required): Type of items - `"queue"` or `"done"`
- `ids` (array, optional): List of specific item IDs to delete. If provided, `status` filter is ignored
- `status` (string, optional): Filter by status (e.g., `"finished"`, `"!finished"`). Required if `ids` not provided
- `remove_file` (boolean, optional): Whether to delete files from disk. Default: `true`.

> [!NOTE]
> `remove_file` is only considered if `YTP_REMOVE_FILES=true` is set. otherwise, files will not be deleted from disk even if `remove_file` is `true`.

**Request Examples**:

**Delete specific items by IDs:**
```json
{
  "type": "done",
  "ids": ["<id1>", "<id2>"],
  "remove_file": true
}
```

**Delete all finished items (filter mode):**
```json
{
  "type": "done",
  "status": "finished",
  "remove_file": true
}
```

**Delete all non-finished items (exclusion filter):**
```json
{
  "type": "done",
  "status": "!finished",
  "remove_file": false
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

**Response (Filter mode with deleted count)**:
```json
{
  "items":{
    "<id1>": "status",
    "<id2>": "status",
    ...
  },
  "deleted": 5
}
```

**Error Responses**:
- `400 Bad Request` if parameters are invalid:
  ```json
  { "error": "type is required." }
  { "error": "either 'ids' or 'status' filter is required." }
  { "error": "type must be 'queue' or 'done'." }
  ```

**Notes**:
- When using filter mode, all matching items will be deleted.
- Filter mode with `{ "status": "!finished" }` is useful for cleaning up failed/pending downloads.
- Filter mode returns a `deleted` count indicating how many items were removed.

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
**Purpose**: Returns the download queue and/or download history with optional pagination support.

**Query Parameters**:
- `type` (optional): Type of items to return. Default: `all`
  - `all` (default): Returns both queue and history (legacy behavior, no pagination)
  - `queue`: Returns only queue items (with pagination)
  - `done`: Returns only history items (with pagination)
- `page` (optional): Page number (1-indexed). Default: `1`. Only used when `type != all`
- `per_page` (optional): Items per page. Default: `config.default_pagination`, Max: `200`. Only used when `type != all`
- `order` (optional): Sort order. Default: `DESC`. Only used when `type != all`
  - `DESC`: Newest items first (descending by creation date)
  - `ASC`: Oldest items first (ascending by creation date)
- `status` (optional): Filter items by status. Only used when `type != all`
  - Use status value to include only items with that status (e.g., `status=finished`)
  - Prefix with `!` to exclude items with that status (e.g., `status=!finished`)
  - Common status values: `finished`, `downloading`, `pending`, `error`

**Response (when `type=all` or no type set)** - Legacy format:
```json
{
  "queue": [
    { 
      "id": "abc123",
      "url": "https://example.com/video",
      "title": "Video Title",
      "status": "downloading",
      ...
    },
    ...
  ],
  "history": [
    {
      "id": "def456", 
      "url": "https://example.com/video2",
      "title": "Completed Video",
      "status": "finished",
      ...
    },
    ...
  ]
}
```

**Response (when `type=queue` or `type=done`)** - Paginated format:
```json
{
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1234,
    "total_pages": 25,
    "has_next": true,
    "has_prev": false
  },
  "items": [
    {
      "id": "abc123",
      "url": "https://example.com/video",
      "title": "Video Title",
      "status": "finished",
      ...
    },
    ...
  ]
}
```

**Error Responses**:
- `400 Bad Request` if parameters are invalid:
  ```json
  { "error": "type must be one of all, queue, done." }
  { "error": "page must be >= 1." }
  { "error": "per_page must be between 1 and 1000." }
  { "error": "order must be ASC or DESC." }
  { "error": "page and per_page must be valid integers." }
  ```

**Notes**:
- The `type=all` behavior is considered legacy and will be removed in future versions
- For large datasets, use paginated requests (`type=queue` or `type=done`) for better performance
- The `items` array contains ItemDTO objects serialized to JSON

**Examples**:
```bash
# Get all finished items from history
GET /api/history?type=done&status=finished

# Get all items except finished ones
GET /api/history?type=done&status=!finished

# Get only downloading items from queue
GET /api/history?type=queue&status=downloading

# Get all items except errors, with pagination
GET /api/history?type=done&status=!error&page=2&per_page=50

# Combine with sorting - oldest pending items first
GET /api/history?type=queue&status=pending&order=ASC
```

---

### GET /api/history/live
**Purpose**: Get live queue data with real-time download progress.

This endpoint returns the current state of active downloads from memory.

**Response**:
```json
{
    "history_count": 0, // total number of completed items in history
    "queue":{
      "id": "abc123",
      "url": "https://example.com/video",
      "title": "Video Title",
      "status": "downloading",
      "progress": 45.6,
      "speed": "2.5 MiB/s",
      "eta": "00:05:23",
      ...
    },
    ...
}
```

---

### POST /api/history/start
**Purpose**: Start one or more downloads in the queue.

**Body**:
```json
{
  "ids": ["<id1>", "<id2>", ...]
}
```

**Response**:
```json
{
  "<id1>": "started",
  "<id2>": "started",
  ...
}
```

**Error Responses**:
- `400 Bad Request` if `ids` is missing or not an array:
  ```json
  { "error": "ids is required and must be an array." }
  ```

**Notes**:
- Items must exist in the queue
- Sets `auto_start: true` for the specified items

---

### POST /api/history/pause
**Purpose**: Pause one or more downloads in the queue.

**Body**:
```json
{
  "ids": ["<id1>", "<id2>", ...]
}
```

**Response**:
```json
{
  "<id1>": "paused",
  "<id2>": "paused",
  ...
}
```

**Error Responses**:
- `400 Bad Request` if `ids` is missing or not an array:
  ```json
  { "error": "ids is required and must be an array." }
  ```

**Notes**:
- Items must exist in the queue
- Sets `auto_start: false` for the specified items

---

### POST /api/history/cancel
**Purpose**: Cancel one or more downloads and move them to history.

**Body**:
```json
{
  "ids": ["<id1>", "<id2>", ...]
}
```

**Response**:
```json
{
  "<id1>": "ok",
  "<id2>": "ok",
  ...
}
```

**Error Responses**:
- `400 Bad Request` if `ids` is missing or not an array:
  ```json
  { "error": "ids is required and must be an array." }
  ```

**Notes**:
- Items must exist in the queue
- Stops active downloads if they are currently running

---

### DELETE /api/history/{id}/archive
**Purpose**: Remove an item from archive file, allowing it to be re-downloaded.

**Path Parameter**:
- `id`: Item ID from the history.

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

### POST /api/history/{id}/archive
**Purpose**: Add item to the archive file preventing it from being downloaded.

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

### GET /api/archiver
**Purpose**: Read entries from the download archive associated with a preset.

**Query Parameters**:
- `preset` (required): Preset name.
- `ids` (optional): Comma-separated list of archive IDs to filter. If omitted, returns all entries.

**Response**:
```json
{
  "file": "/path/to/archive.log",
  "items": ["youtube ABC123", "vimeo XYZ789"],
  "count": 2
}
```
or an error:
```json
{ "error": "Preset '<name>' does not provide a download_archive." }
```

- `400 Bad Request` if `preset` is missing/invalid or the preset has no `download_archive`.

---

### POST /api/archiver
**Purpose**: Append archive IDs to the download archive resolved by a preset.

**Body**:
```json
{
  "preset": "<preset-name>",
  "items": ["youtube ABC123", "vimeo XYZ789"],
  "skip_check": false
}
```

**Response**:
```json
{
  "file": "/path/to/archive.log",
  "status": true,
  "items": ["youtube ABC123", "vimeo XYZ789"]
}
```
Notes:
- Returns `200 OK` if any new entries were added, `304 Not Modified` if no-op (all already present or invalid).
- `400 Bad Request` if `preset` is missing/invalid, the preset has no `download_archive`, or `items` is empty.

---

### DELETE /api/archiver
**Purpose**: Remove archive IDs from the download archive resolved by a preset.

**Body**:
```json
{
  "preset": "<preset-name>",
  "items": ["youtube ABC123", "vimeo XYZ789"]
}
```

**Response**:
```json
{
  "file": "/path/to/archive.log",
  "status": true,
  "items": ["youtube ABC123", "vimeo XYZ789"]
}
```
Notes:
- Returns `200 OK` if the archive file changed, `304 Not Modified` if it was unchanged.
- `400 Bad Request` if `preset` is missing/invalid, the preset has no `download_archive`, or `items` is empty.

---

### GET /api/tasks
**Purpose**: Retrieves the scheduled tasks.  

**Query Parameters**:
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "My Task",
      "url": "https://youtube.com/...",
      "timer": "5 */2 * * *",
      "cookies": "",
      "config": {},
      "template": "...",
      "folder": "...",
      "preset": "...",
      "auto_start": true,
      "handler_enabled": true,
      "enabled": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### POST /api/tasks
**Purpose**: Create a new scheduled task.

**Body**: Task object. Example:
```json
{
  "name": "My Task",
  "url": "https://youtube.com/...",
  "timer": "5 */2 * * *",
  "cookies": "",
  "config": {},
  "template": "...",
  "folder": "...",
  "preset": "...",
  "auto_start": true,
  "handler_enabled": true,
  "enabled": true
}
```

**Response**:
```json
{
  "id": 1,
  "name": "My Task",
  "url": "https://youtube.com/...",
  "timer": "5 */2 * * *",
  "cookies": "",
  "config": {},
  "template": "...",
  "folder": "...",
  "preset": "...",
  "auto_start": true,
  "handler_enabled": true,
  "enabled": true
}
```

**Error Responses**:
- `400 Bad Request` - Invalid request body or validation error
- `409 Conflict` - Task with the same name already exists

---

### GET /api/tasks/{id}
**Purpose**: Retrieve a specific task by ID.

**Path Parameter**:
- `id`: Task ID.

**Response**:
```json
{
  "id": 1,
  "name": "My Task",
  "url": "https://youtube.com/...",
  "timer": "5 */2 * * *",
  "cookies": "",
  "config": {},
  "template": "...",
  "folder": "...",
  "preset": "...",
  "auto_start": true,
  "handler_enabled": true,
  "enabled": true
}
```

**Error Responses**:
- `400 Bad Request` - ID is missing
- `404 Not Found` - Task does not exist

---

### DELETE /api/tasks/{id}
**Purpose**: Delete a scheduled task by ID.

**Path Parameter**:
- `id`: Task ID.

**Response**:
```json
{
  "id": 1,
  "name": "Deleted Task",
  "url": "https://youtube.com/...",
  "timer": "5 */2 * * *",
  "cookies": "",
  "config": {},
  "template": "...",
  "folder": "...",
  "preset": "...",
  "auto_start": true,
  "handler_enabled": true,
  "enabled": true
}
```

**Error Responses**:
- `400 Bad Request` - ID is missing
- `404 Not Found` - Task does not exist

---

### PATCH /api/tasks/{id}
**Purpose**: Partially update a scheduled task.

**Path Parameter**:
- `id`: Task ID.

**Request Body**:
JSON object with fields to update:
```json
{
  "enabled": false,
  "timer": "0 */6 * * *"
}
```

**Notes**:
- Only include fields you want to update
- All fields are optional

**Response**: Returns the updated task object.

**Error Responses**:
- `400 Bad Request` - ID is missing, invalid JSON, or validation error
- `404 Not Found` - Task does not exist
- `409 Conflict` - Task name conflict

---

### PUT /api/tasks/{id}
**Purpose**: Replace an existing scheduled task.

**Path Parameter**:
- `id`: Task ID.

**Request Body**: Full task object:
```json
{
  "name": "Updated Task",
  "url": "https://youtube.com/...",
  "timer": "0 */6 * * *",
  "cookies": "",
  "config": {},
  "template": "...",
  "folder": "...",
  "preset": "...",
  "auto_start": true,
  "handler_enabled": true,
  "enabled": true
}
```

**Response**: Returns the updated task object.

**Error Responses**:
- `400 Bad Request` - ID is missing, invalid JSON, or validation error
- `404 Not Found` - Task does not exist
- `409 Conflict` - Task name conflict

---

### POST /api/tasks/inspect
**Purpose**: Preview which handler matches a URL and review the items it would queue without dispatching downloads.

**Body**:
```json
{
  "url": "https://example.com/feed",            // required, validated URL
  "preset": "news-preset",                     // optional preset override - In real scenarios, the preset come from the task.
  "handler": "GenericTaskHandler",              // optional explicit handler class name, in real scenarios, the handler is resolved automatically.
  "static_only": false                          // optional, if true performs only can_handle check without extracting items (faster, lightweight)
}
```

**Notes**:
- When `static_only` is `true`, the endpoint only checks if a handler can process the URL using the `can_handle` method
- This is much faster and lighter than the full inspection which calls the handler's `extract` method
- Use `static_only: true` for quick validation checks (e.g., UI indicators)
- Use `static_only: false` (default) for full inspection with item extraction

**Response (success with static_only: true)**:
```json
{
  "items": [],
  "metadata": {
    "matched": true,
    "handler": "GenericTaskHandler"
  }
}
```

**Response (success with static_only: false)**:
```json
{
  "matched": true,
  "handler": "GenericTaskHandler",
  "supported": true,
  "items": [
    {
      "url": "https://example.com/video/1",
      "title": "Example title",
      "archive_id": "generic 1",
      "metadata": {
        "source_id": "...",
        "source_name": "...",
        "source_handler": "GenericTaskHandler"
      }
    }
  ],
  "metadata": {
    "raw_count": 3
  }
}
```

- Returns `200 OK` when inspection succeeds.
- The `metadata` object is optional and may contain handler-specific keys.

**Response (failure)**:
```json
{
  "matched": false,
  "handler": null,
  "error": "No handler matched the supplied URL.",
  "message": "No handler matched the supplied URL.",
  "metadata": {
    "supported": true
  }
}
```

- Returns `400 Bad Request` when the handler cannot process the URL or inspection fails.
- When a handler is specified but does not support manual inspection, `supported` is `false` and the `message` explains the limitation.

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

### DELETE /api/tasks/{id}/mark
**Purpose**: Remove all entries associated with a scheduled task from the download archive, allowing them to be re-downloaded.

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

### POST /api/tasks/{id}/metadata
**Purpose**: Generate metadata files for a scheduled task, including NFO files, thumbnails, and JSON metadata compatible with media centers.

**Path Parameter**:
- `id`: Task ID.

**Response**:
```json
{
  "id": "channel_or_playlist_id",
  "id_type": "youtube|twitch|...",
  "title": "Channel/Playlist Title",
  "description": "Description text...",
  "uploader": "Uploader name",
  "tags": ["tag1", "tag2"],
  "year": 2024,
  "json_file": "path/to/Title [id].info.json",
  "nfo_file": "path/to/tvshow.nfo",
  "thumbnails": {
    "poster": "path/to/poster.jpg",
    "fanart": "path/to/fanart.jpg",
    "thumb": "path/to/thumb.jpg",
    "banner": "path/to/banner.jpg",
    "icon": "path/to/icon.jpg",
    "landscape": "path/to/landscape.jpg"
  }
}
```
or
```json
{ "error": "..." }
```

**Files Generated**:
- `tvshow.nfo` - NFO file for media center compatibility (Kodi, Jellyfin, Emby, etc.)
- `Title [id].info.json` - yt-dlp metadata file.
- `poster.jpg`, `fanart.jpg`, `thumb.jpg`, `banner.jpg`, `icon.jpg`, `landscape.jpg` - Thumbnail images (if available from the source)

**Notes**:
- This endpoint fetches metadata from the URL associated with the task
- Files are saved to the task's configured folder (or default download path)
- Existing files will be overwritten.
- Thumbnail images are only downloaded if available from the source.
- The NFO file follows the Kodi tvshow.nfo format

**Status Codes**:
- `200 OK` - Metadata generated successfully
- `400 Bad Request` - Missing task ID, invalid folder path, or failed to fetch metadata
- `404 Not Found` - Task does not exist

---

### GET /api/tasks/definitions/
**Purpose**: Retrieve task definitions.

**Query Parameters**:
- `include=definition` (optional) - Include the full definition object in response.
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "Task Definition Name",
      "description": "...",
      "enabled": true,
      "definition": { ... }  // only if include=definition
    },
    ...
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### GET /api/tasks/definitions/{id}
**Purpose**: Retrieve a specific task definition by ID.

**Path Parameter**:
- `id`: Task definition ID.

**Response**:
```json
{
  "id": 1,
  "name": "Task Definition Name",
  "description": "...",
  "enabled": true,
  "definition": {
    "parse": {
      "url": { ... },
      "items": { ... }
    },
    "engine": { ... },
    "request": { ... },
    "response": { ... }
  }
}
```

- `400 Bad Request` if ID is missing.
- `404 Not Found` if the task definition doesn't exist.

---

### POST /api/tasks/definitions/
**Purpose**: Create a new task definition.

**Body**:
```json
{
  "name": "My Task Definition",
  "description": "...",
  "enabled": true,
  "definition": {
    "parse": {
      "url": { ... },
      "items": { ... }
    },
    "engine": { ... },
    "request": { ... },
    "response": { ... }
  }
}
```

**Response**:
```json
{
  "id": 1,
  "name": "My Task Definition",
  "description": "...",
  "enabled": true,
  "definition": { ... }
}
```

- `201 Created` if successful.
- `400 Bad Request` if validation fails.

---

### PUT /api/tasks/definitions/{id}
**Purpose**: Replace an existing task definition.

**Path Parameter**:
- `id`: Task definition ID.

**Body**:
```json
{
  "name": "Updated Name",
  "description": "...",
  "enabled": false,
  "definition": {
    "parse": { ... },
    "engine": { ... },
    "request": { ... },
    "response": { ... }
  }
}
```

**Response**:
```json
{
  "id": 1,
  "name": "Updated Name",
  "description": "...",
  "enabled": false,
  "definition": { ... }
}
```

- `200 OK` if successful.
- `400 Bad Request` if ID is missing or validation fails.
- `404 Not Found` if the task definition doesn't exist.

---

### PATCH /api/tasks/definitions/{id}
**Purpose**: Partially update a task definition.

**Path Parameter**:
- `id`: Task definition ID.

**Body**:
```json
{
  "enabled": false,
  "description": "Updated description"
}
```

**Response**: Updated task definition object.

- `200 OK` if successful.
- `400 Bad Request` if ID is missing or validation fails.
- `404 Not Found` if the task definition doesn't exist.

---

### DELETE /api/tasks/definitions/{id}
**Purpose**: Delete a task definition.

**Path Parameter**:
- `id`: Task definition ID.

**Response**:
```json
{
  "id": 1,
  "name": "Deleted Definition",
  "description": "...",
  "enabled": false,
  "definition": { ... }
}
```

- `200 OK` if successful.
- `400 Bad Request` if ID is missing.
- `404 Not Found` if the task definition doesn't exist.

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

### POST /api/file/actions
**Purpose**: Perform file browser actions on files or directories.

**Body**:
```json
[
  { "action": "rename", "path": "relative/path/file.ext", "new_name": "new_name.ext" },
  { "action": "delete", "path": "relative/path/file.ext" },
  { "action": "move", "path": "relative/path/file.ext", "new_path": "new/relative/path" },
  { "action": "directory", "path": "relative/path", "new_dir": "subdirectory" }
]
```

Actions and required fields:
- `rename`: `{ "action": "rename", "path": "...", "new_name": "<name>" }`
- `delete`: `{ "action": "delete", "path": "..." }`
- `move`: `{ "action": "move", "path": "...", "new_path": "<dir-relative-to-download_path>" }`
- `directory`: `{ "action": "directory", "path": "...", "new_dir": "<subdir/to/create>" }`

**Response**: 
```json
[
  { "path": "relative/path", "action": "rename", "ok": true },
  { "path": "relative/path", "action": "delete", "ok": true },
  ...
]
```

or an error:
```json
{ "error": "text" }
```

- `403 Forbidden` if browser actions are disabled.
- `400 Bad Request` for invalid actions or parameters.

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

### GET /api/download/{filename}
**Purpose**: Serve downloaded files directly from the download path.

**Path Parameter**:
- `filename`: Relative path to the file within the download directory (URL-encoded).

**Response**:
- `200 OK` with file content and appropriate headers
- `302 Found` redirect if the file path needs normalization
- `404 Not Found` if the file doesn't exist

- **Error Responses**  

When an error occurs, responses follow a structure similar to:
```json
{ "error": "Description of the error"  }
```
with an appropriate HTTP status code.

---

### GET /api/random/background
**Purpose**: Get a random background image from configured backends.  

**Query Parameters**:
- `force=true` (optional) - Force fetch a new image instead of using cache.

**Response**:
Binary image data with appropriate headers

---

### GET /api/presets
**Purpose**: Retrieve available presets.

**Query Parameters**:
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "preset_name",
      "description": "...",
      "folder": "my_channel/foo",
      "template": "%(title)s.%(ext)s",
      "cookies": "...",
      "cli": "--write-subs --embed-subs",
      "default": true
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

**Notes**:
- `default: true` indicates this is a system default preset (cannot be modified or deleted)

---

### GET /api/presets/{id}
**Purpose**: Retrieve a specific preset by ID.

**Path Parameter**:
- `id`: Preset ID.

**Response**:
```json
{
  "id": 1,
  "name": "preset_name",
  "description": "...",
  "folder": "my_channel/foo",
  "template": "%(title)s.%(ext)s",
  "cookies": "...",
  "cli": "--write-subs --embed-subs",
  "default": false
}
```

**Error Responses**:
- `400 Bad Request` - ID is missing
- `404 Not Found` - Preset not found

---

### POST /api/presets
**Purpose**: Create a new download preset.

**Body**:
```json
{
  "name": "My Preset",
  "description": "...",
  "folder": "my_channel/foo",
  "template": "%(title)s.%(ext)s",
  "cookies": "...",
  "cli": "--write-subs --embed-subs"
}
```

**Response**:
```json
{
  "id": 1,
  "name": "My Preset",
  "description": "...",
  "folder": "my_channel/foo",
  "template": "%(title)s.%(ext)s",
  "cookies": "...",
  "cli": "--write-subs --embed-subs",
  "default": false
}
```

**Error Responses**:
- `400 Bad Request` - Invalid request body or validation error

---

### PATCH /api/presets/{id}
**Purpose**: Partially update a preset.

**Path Parameter**:
- `id`: Preset ID.

**Body**:
```json
{
  "description": "Updated description",
  "cli": "--write-subs --embed-subs --format best"
}
```

**Notes**:
- Only include fields you want to update
- All fields are optional
- Default presets cannot be modified

**Response**: Returns the updated preset object.

**Error Responses**:
- `400 Bad Request` - ID is missing, invalid JSON, validation error, or attempting to modify default preset
- `404 Not Found` - Preset not found
- `409 Conflict` - Preset name conflict

---

### PUT /api/presets/{id}
**Purpose**: Replace an existing preset.

**Path Parameter**:
- `id`: Preset ID.

**Body**: Full preset object:
```json
{
  "name": "Updated Preset",
  "description": "...",
  "folder": "my_channel/foo",
  "template": "%(title)s.%(ext)s",
  "cookies": "...",
  "cli": "--write-subs --embed-subs"
}
```

**Notes**:
- Default presets cannot be modified

**Response**: Returns the updated preset object.

**Error Responses**:
- `400 Bad Request` - ID is missing, invalid JSON, validation error, or attempting to modify default preset
- `404 Not Found` - Preset not found
- `409 Conflict` - Preset name conflict

---

### DELETE /api/presets/{id}
**Purpose**: Delete a preset by ID.

**Path Parameter**:
- `id`: Preset ID.

**Response**: Returns the deleted preset object.

**Error Responses**:
- `400 Bad Request` - ID is missing or attempting to delete default preset
- `404 Not Found` - Preset not found

---

### GET /api/dl_fields/
**Purpose**: Retrieve download fields with pagination.

**Query Parameters**:
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    { "id": 1, "name": "...", "description": "...", "field": "...", "kind": "text", "order": 0, "value": "", "extras": {} }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### POST /api/dl_fields/
**Purpose**: Create a new download field.

**Body**:
```json
{
  "name": "Title",
  "description": "...",
  "field": "title",
  "kind": "text",
  "order": 0,
  "value": "",
  "icon": "fa-solid fa-tag",
  "extras": {}
}
```

**Response**:
```json
{ "id": 1, "name": "Title", "description": "...", "field": "title", "kind": "text", "order": 0, "value": "", "icon": "fa-solid fa-tag", "extras": {} }
```

---

### GET /api/dl_fields/{id}
**Purpose**: Retrieve a single download field by ID.

**Path Parameter**:
- `id`: Download field ID.

**Response**:
```json
{ "id": 1, "name": "Title", "description": "...", "field": "title", "kind": "text", "order": 0, "value": "", "icon": "fa-solid fa-tag", "extras": {} }
```

---

### PATCH /api/dl_fields/{id}
**Purpose**: Partially update a download field.

**Path Parameter**:
- `id`: Download field ID.

**Body**:
```json
{ "description": "Updated description", "order": 1 }
```

**Response**: Updated download field object.

---

### PUT /api/dl_fields/{id}
**Purpose**: Replace a download field.

**Path Parameter**:
- `id`: Download field ID.

**Body**:
```json
{
  "name": "Title",
  "description": "...",
  "field": "title",
  "kind": "text",
  "order": 0,
  "value": "",
  "icon": "fa-solid fa-tag",
  "extras": {}
}
```

**Response**: Updated download field object.

---

### DELETE /api/dl_fields/{id}
**Purpose**: Delete a download field by ID.

**Path Parameter**:
- `id`: Download field ID.

**Response**:
```json
{ 
  "id": 1, 
  "name": "Title", 
  "description": "...", 
  "field": "title", 
  "kind": "text",   
  "order": 0, 
  "value": "", 
  "icon": "fa-solid fa-tag", 
  "extras": {} 
}
```

---

### GET /api/conditions/
**Purpose**: Retrieve download conditions with pagination.

**Query Parameters**:
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "condition_name",
      "filter": "...",
      "cli": "...",
      "extras": {},
      "enabled": true,
      "priority": 0,
      "description": "What this condition does"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

**Notes**:
- Conditions are evaluated in priority order (higher priority first).
- Priority defaults to 0 when not specified.
- IDs are integer values generated by the database.

---

### POST /api/conditions/
**Purpose**: Create a new download condition.

**Body**:
```json
{
  "name": "Use proxy for region locked content",
  "filter": "availability = 'needs_auth' & channel_id = 'channel_id'",
  "cli": "--proxy http://myproxy.com:8080",
  "extras": {},
  "enabled": true,
  "priority": 10,
  "description": "Apply proxy for region-locked videos"
}
```

**Response**: Created condition object.

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

### GET /api/conditions/{id}
**Purpose**: Retrieve a condition by ID.

**Path Parameter**:
- `id`: Condition ID.

**Response**: Condition object.

---

### PATCH /api/conditions/{id}
**Purpose**: Partially update a condition.

**Path Parameter**:
- `id`: Condition ID.

**Body**:
```json
{ "enabled": false, "priority": 5 }
```

**Response**: Updated condition object.

---

### PUT /api/conditions/{id}
**Purpose**: Replace a condition.

**Path Parameter**:
- `id`: Condition ID.

**Body**: Full condition object.

**Response**: Updated condition object.

---

### DELETE /api/conditions/{id}
**Purpose**: Delete a condition by ID.

**Path Parameter**:
- `id`: Condition ID.

**Response**: Deleted condition object.

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

### GET /api/logs/stream
**Purpose**: Stream live log lines via Server-Sent Events (SSE).  

**Response**:
- `Content-Type: text/event-stream`
- Emits `log_lines` events with a log line payload.

**Event Payload**:
```json
{
  "id": "<sha256>",
  "line": "<log line>",
  "datetime": "2024-01-01T12:00:00.000000+00:00"
}
```

- Returns `404 Not Found` if file logging is not enabled or the log file is missing.

---

### GET /api/notifications/
**Purpose**: Retrieve notification targets with pagination.

**Query Parameters**:
- `page` (optional): Page number (1-indexed). Default: `1`.
- `per_page` (optional): Items per page. Default: `config.default_pagination`.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "name": "My Webhook",
      "on": ["item_completed"],
      "presets": ["default"],
      "enabled": true,
      "request": {
        "type": "json",
        "method": "POST",
        "url": "https://example.com/webhook",
        "data_key": "data",
        "headers": [{ "key": "Authorization", "value": "Bearer ..." }]
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

**Notes**:
- Empty `on` and `presets` arrays mean all events/presets.
- `request.method` supports `POST` and `PUT`.
- `request.type` supports `json` and `form`.
- IDs are integer values generated by the database.

---

### GET /api/notifications/events/
**Purpose**: Retrieve allowed notification event names.

**Response**:
```json
{ "events": ["item_added", "item_completed", "log_error", "test"] }
```

---

### POST /api/notifications/
**Purpose**: Create a notification target.

**Body**:
```json
{
  "name": "My Webhook",
  "on": ["item_completed"],
  "presets": ["default"],
  "enabled": true,
  "request": {
    "type": "json",
    "method": "POST",
    "url": "https://example.com/webhook",
    "data_key": "data",
    "headers": [{ "key": "Authorization", "value": "Bearer ..." }]
  }
}
```

**Response**: Created notification target.

---

### GET /api/notifications/{id}
**Purpose**: Retrieve a notification target by ID.

**Path Parameter**:
- `id`: Notification target ID.

**Response**: Notification target object.

---

### PATCH /api/notifications/{id}
**Purpose**: Partially update a notification target.

**Path Parameter**:
- `id`: Notification target ID.

**Body**:
```json
{ "enabled": false }
```

**Response**: Updated notification target.

---

### PUT /api/notifications/{id}
**Purpose**: Replace a notification target.

**Path Parameter**:
- `id`: Notification target ID.

**Body**: Full notification target object.

**Response**: Updated notification target.

---

### DELETE /api/notifications/{id}
**Purpose**: Delete a notification target.

**Path Parameter**:
- `id`: Notification target ID.

**Response**: Deleted notification target.

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
{}
```

---

### GET /api/yt-dlp/options
**Purpose**: Get the current yt-dlp CLI options as a JSON object.

**Response**: JSON object with yt-dlp options and metadata.

---

### GET /api/system/configuration
**Purpose**: Retrieve comprehensive system configuration including app settings, presets, download fields, queue status, and folder structure.

**Response**:
```json
{
  "app": {
    "version": "...",
    "download_path": "/path/to/downloads",
    "base_path": "/",
    ...
  },
  "presets": [
    {
      "id": 1,
      "name": "default",
      "description": "...",
      ...
    }
  ],
  "dl_fields": [
    {
      "id": 1,
      "name": "Title",
      "field": "title",
      "kind": "text",
      ...
    }
  ],
  "paused": false,
  "folders": [
    {"name": "folder1", "path": "folder1"},
    {"name": "folder2", "path": "folder2"}
  ],
  "history_count": 150,
  "queue": [
    {
      "id": "abc123",
      "url": "https://example.com/video",
      "status": "pending",
      ...
    }
  ]
}
```

**Notes**:
- This endpoint combines multiple data sources into a single response for efficient initialization
- The `folders` array includes available download folders up to the configured depth limit
- The `queue` array contains active download items

---

### POST /api/system/terminal
**Purpose**: Stream yt-dlp CLI output via Server-Sent Events (SSE). Requires `YTP_CONSOLE_ENABLED=true`.

**Body**:
```json
{
  "command": "--help"
}
```

**Response**:
- `Content-Type: text/event-stream`
- Emits `output` events for stdout/stderr and a final `close` event when the process exits.

**Event Payloads**:
```json
{ "type": "stdout", "line": "<output line>" }
```
```json
{ "exitcode": 0 }
```

- `403 Forbidden` if console is disabled.
- `400 Bad Request` if the request body is invalid.

---

### POST /api/system/pause
**Purpose**: Pause all non-active downloads in the queue.

**Response**:
```json
{ "message": "Non-active downloads have been paused." }
```

- `200 OK` if downloads were successfully paused.
- `406 Not Acceptable` if downloads are already paused.

---

### POST /api/system/resume
**Purpose**: Resume all paused downloads in the queue.

**Response**:
```json
{ "message": "Resumed all downloads." }
```

- `200 OK` if downloads were successfully resumed.
- `406 Not Acceptable` if downloads are not paused.

---

### POST /api/system/shutdown
**Purpose**: Gracefully shut down the application (native mode only).

**Response**:
```json
{ "message": "The application shutting down." }
```

- `400 Bad Request` if not running in native mode.

---

### POST /api/system/check-updates
**Purpose**: Manually trigger a check for application updates from GitHub releases.

**Response**:
```json
{
  "status": "update_available",
  "current_version": "v1.0.14",
  "new_version": "v1.0.15"
}
```

**Status values**:
- `disabled`: Update checking is disabled in configuration
- `up_to_date`: No updates available
- `update_available`: New version is available
- `error`: Error occurred during check (HTTP error, network issue, etc.)

- `400 Bad Request` if update checking is disabled in configuration (`check_for_updates: false`).
- `new_version` will be `null` when status is `up_to_date`, `disabled`, or `error`.
- The check runs synchronously and returns the result immediately.
- Results are also stored in config and pushed to frontend via WebSocket.

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

### GET /api/docs/{file}
**Purpose**: Serve documentation files from the GitHub repository.

**Path Parameter**:
- `file`: Documentation filename (e.g., `README.md`, `FAQ.md`, `API.md`, `sc_short.jpg`, `sc_simple.jpg`)

**Response**:
- File content with appropriate `Content-Type` header (text/markdown for .md, image/jpeg for .jpg, etc.)
- Cached for 1 hour

or an error:
```json
{ "error": "Doc file not found." }
```

- `404 Not Found` if the file is not in the allowed list.
- `500 Internal Server Error` if fetching from GitHub fails.

> **Note**: This endpoint also responds to direct file paths like `/README.md`, `/FAQ.md`, etc. without the `/api/docs/` prefix.

---

## WebSocket API

### Connection

**Endpoint**: `/ws` (or `{base_path}/ws` if base_path is configured)

The WebSocket API provides real-time bidirectional communication between the client and server for download queue management and status updates.

**Connection Details**:
- Protocol: WebSocket (ws:// or wss://)
- Heartbeat: 10-second interval
- Auto-reconnect: Client should implement reconnection logic

**Example Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Event:', message.event, 'Data:', message.data);
};
```

---

### Authentication

WebSocket connections use the same authentication as HTTP endpoints. If `YTP_AUTH_USERNAME` and `YTP_AUTH_PASSWORD` are set, authentication can be provided via:

1. **Query Parameter** (recommended for WebSocket):
   ```
   ws://localhost:8080/ws?apikey=<base64_urlsafe_credentials>
   ```

2. **HTTP Basic Auth header** (during WebSocket handshake):
   ```
   Authorization: Basic base64("<username>:<password>")
   ```

---

### Message Format

All WebSocket messages use JSON format with `event` and `data` fields:

**Client → Server**:
```json
{
  "event": "event_name",
  "data": { /* payload */ }
}
```

**Server → Client**:
```json
{
  "event": "event_name",
  "data": { /* Event object */ }
}
```

---

### Client Events (Client → Server)

These events can be sent by the client to control downloads and queue operations.

#### `add_url`

Add a new URL to the download queue.

**Request**:
```json
{
  "event": "add_url",
  "data": {
    "url": "https://youtube.com/watch?v=...",
    "preset": "default",
    "folder": "my_channel/foo",
    "template": "%(title)s.%(ext)s",
    "cookies": "...",
    "cli": "--write-subs --embed-subs",
    "auto_start": true
  }
}
```

**Required Fields**:
- `url` - The video URL to download

**Optional Fields**:
- `preset` - Preset name to use
- `folder` - Output folder relative to download_path
- `template` - Filename template
- `cookies` - Authentication cookies (Netscape format)
- `cli` - Additional yt-dlp CLI arguments
- `auto_start` - Whether to auto-start the download (default: true)

**Response Events**:
- `item_status` - Item added successfully
- `log_error` - Error adding URL

---

#### `item_cancel`

Cancel an active or pending download.

**Request**:
```json
{
  "event": "item_cancel",
  "data": "item_id"
}
```

**Required**: Item ID (string)

**Response Events**:
- `item_cancelled` - Item cancelled successfully
- `log_error` - Error cancelling item

---

#### `item_delete`

Delete a download item and optionally remove its files.

**Request**:
```json
{
  "event": "item_delete",
  "data": {
    "id": "item_id",
    "remove_file": true
  }
}
```

**Required Fields**:
- `id` - The item ID to delete

**Optional Fields**:
- `remove_file` - Whether to delete downloaded files (default: false)

**Response Events**:
- `item_deleted` - Item deleted successfully
- `log_error` - Error deleting item

---

#### `item_start`

Start one or more paused download items.

**Request** (single item):
```json
{
  "event": "item_start",
  "data": "item_id"
}
```

**Request** (multiple items):
```json
{
  "event": "item_start",
  "data": ["item_id1", "item_id2", "item_id3"]
}
```

**Required**: Item ID(s) - string or array of strings

**Response Events**:
- `item_updated` - Items started successfully
- `log_error` - Error starting items

---

#### `item_pause`

Pause one or more active download items.

**Request** (single item):
```json
{
  "event": "item_pause",
  "data": "item_id"
}
```

**Request** (multiple items):
```json
{
  "event": "item_pause",
  "data": ["item_id1", "item_id2", "item_id3"]
}
```

**Required**: Item ID(s) - string or array of strings

**Response Events**:
- `item_updated` - Items paused successfully
- `log_error` - Error pausing items

---

### Server Events (Server → Client)

These events are emitted by the server and sent to connected WebSocket clients.

#### Connection Events

##### `config_update`

Emitted when system configuration changes (presets, tasks, conditions, etc.).

**Event**:
```json
{
  "event": "config_update",
  "data": {
    "feature": "presets|tasks|conditions|notifications|dl_fields",
    "action": "create|update|delete",
    "data": { /* Updated object */ }
  }
}
```

---

##### `connected`

Emitted when a client successfully connects to the WebSocket.

**Event**:
```json
{
  "event": "connected",
  "data": {
    "sid": "session_id",
    "timestamp": 1234567890.123
  }
}
```

---

##### `active_queue`

Emitted periodically with the current active queue status.

**Event**:
```json
{
  "event": "active_queue",
  "data": {
    "queue": [
      {
        "id": "abc123",
        "status": "downloading",
        "progress": 45.6,
        ...
      }
    ]
  }
}
```

---

#### Logging Events

##### `log_info`

Informational log message.

**Event**:
```json
{
  "event": "log_info",
  "data": {
    "title": "Info Title",
    "message": "Informational message",
    "timestamp": 1234567890.123
  }
}
```

---

##### `log_success`

Success log message.

**Event**:
```json
{
  "event": "log_success",
  "data": {
    "title": "Success Title",
    "message": "Operation completed successfully",
    "timestamp": 1234567890.123
  }
}
```

---

##### `log_warning`

Warning log message.

**Event**:
```json
{
  "event": "log_warning",
  "data": {
    "title": "Warning Title",
    "message": "Warning message",
    "timestamp": 1234567890.123
  }
}
```

---

##### `log_error`

Error log message.

**Event**:
```json
{
  "event": "log_error",
  "data": {
    "title": "Error Title",
    "message": "Error details",
    "timestamp": 1234567890.123
  }
}
```

---

#### Download Queue Events

##### `item_added`

Emitted when a new item is added to the download queue.

**Event**:
```json
{
  "event": "item_added",
  "data": {
    "id": "abc123",
    "url": "https://example.com/video",
    "title": "Video Title",
    "status": "pending",
    "preset": "default",
    ...
  }
}
```

---

##### `item_updated`

Emitted when a download item's status or progress updates (high-frequency event).

**Event**:
```json
{
  "event": "item_updated",
  "data": {
    "id": "abc123",
    "status": "downloading",
    "progress": 45.6,
    "speed": "2.5 MiB/s",
    "eta": "00:05:23",
    ...
  }
}
```

---

##### `item_cancelled`

Emitted when a download is cancelled.

**Event**:
```json
{
  "event": "item_cancelled",
  "data": {
    "id": "abc123",
    "status": "cancelled",
    ...
  }
}
```

---

##### `item_deleted`

Emitted when a download item is deleted from the queue or history.

**Event**:
```json
{
  "event": "item_deleted",
  "data": {
    "id": "abc123"
  }
}
```

---

##### `item_moved`

Emitted when a download item is moved between queue and history.

**Event**:
```json
{
  "event": "item_moved",
  "data": {
    "id": "abc123",
    "from": "queue",
    "to": "done"
  }
}
```

---

##### `item_status`

Emitted with status updates for specific operations.

**Event**:
```json
{
  "event": "item_status",
  "data": {
    "id": "abc123",
    "status": "queued",
    "message": "Item added to queue",
    ...
  }
}
```

---

##### `paused`

Emitted when the download queue is paused.

**Event**:
```json
{
  "event": "paused",
  "data": {
    "paused": true,
    "at": 1234567890.123
  }
}
```

---

##### `resumed`

Emitted when the download queue is resumed.

**Event**:
```json
{
  "event": "resumed",
  "data": {
    "paused": false,
    "at": 1234567890.123
  }
}
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
