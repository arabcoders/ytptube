# HTTP API Documentation

This document describes the available endpoints and their usage. All endpoints return JSON responses (unless otherwise specified) and may require certain parameters (query, body, or path). Some endpoints serve static or streaming content (e.g., `.ts`, `.m3u8`, `.vtt` files).

> **Note**: If Basic Authentication is configured (via `auth_username` and `auth_password` in your configuration), you must include an `Authorization: Basic <base64-encoded-credentials>` header or use `?apikey=<base64-encoded-credentials>` query parameter (fallback) in every request.

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
    - [GET /api/history](#get-apihistory)
    - [GET /api/tasks](#get-apitasks)
    - [PUT /api/tasks](#put-apitasks)
    - [GET /api/workers](#get-apiworkers)
    - [POST /api/workers](#post-apiworkers)
    - [PATCH /api/workers/{id}](#patch-apiworkersid)
    - [DELETE /api/workers/{id}](#delete-apiworkersid)
    - [GET /api/player/playlist/{file:.\*}.m3u8](#get-apiplayerplaylistfilem3u8)
    - [GET /api/player/m3u8/{mode}/{file:.\*}.m3u8](#get-apiplayerm3u8modefilem3u8)
    - [GET /api/player/segments/{segment}/{file:.\*}.ts](#get-apiplayersegmentssegmentfilets)
    - [GET /api/player/subtitle/{file:.\*}.vtt](#get-apiplayersubtitlefilevtt)
    - [GET /api/thumbnail](#get-apithumbnail)
    - [GET /api/file/ffprobe/{file:.\*}](#get-apifileffprobefile)
    - [GET /api/youtube/auth](#get-apiyoutubeauth)
    - [GET /api/notifications](#get-apinotifications)
    - [PUT /api/notifications](#put-apinotifications)
    - [POST /api/notifications/test](#post-apinotificationstest)
  - [Error Responses](#error-responses)

---

## Authentication

If `Config.auth_username` and `Config.auth_password` are set, all API requests must include a valid credential using one of the following:

1. HTTP Basic Auth header:

   ```
   Authorization: Basic base64_urlsafe("<username>:<password>")
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
    "message": "More details if available"
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
**Purpose**: Convert a string of yt-dlp or youtube-dl CLI arguments into a JSON-friendly structure.

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
    "postprocessors": [
        {
            "already_have_subtitle": true,
            "key": "FFmpegEmbedSubtitle"
        }
    ],
    "writesubtitles": true
}
```
or an error:
```json
{
  "error": "Failed to convert args. '<reason>'."
}
```

---

### GET /api/yt-dlp/url/info
**Purpose**: Retrieves metadata (info) for a provided URL without adding it to the download queue.

**Query Parameters**:
- `?url=<video-url>`

**Response** (example):
```json
{
  "title": "...",
  "duration": 123.4,
  "extractor": "youtube",
  "_cached": {
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

---

### POST /api/history
**Purpose**: Add one or multiple items (URLs) to the download queue via JSON body.  

**Body**:
```json
// Single item
{
  "url": "https://youtube.com/watch?v=...",
  "preset": "default",
  "folder": "folder relative to download_path",
  "cookies": "...",
  "template": "...",
  "cli": "--write-subs --embed-subs",
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
  "remove_file": true | false   // optional, defaults to false, whether to delete the file from disk.
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

### GET /api/workers
**Purpose**: Returns the status of the worker pool and all workers.  

**Response**:
```json
{
  "open": true|false,
  "count": 4,
  "workers": [
    {
      "id": "worker-1",
      "data": { "status": "downloading", ... }
    },
    {
      "id": "worker-2",
      "data": { "status": "Waiting for download." }
    },
    ...
  ]
}
```
- `open`: Indicates if there are any available workers.  
- `count`: Total number of available workers.

---

### POST /api/workers
**Purpose**: Restart the entire worker pool.  

**Response**:
```json
{
  "message": "Workers pool being restarted."
}
```

---

### PATCH /api/workers/{id}
**Purpose**: Restart a single worker by ID.  

**Path Parameter**:
- `id` = The worker ID.

**Response**:
```json
{
  "status": "restarted"
}
```
or
```json
{
  "status": "in_error_state"
}
```

---

### DELETE /api/workers/{id}
**Purpose**: Stop a single worker by ID.  

**Path Parameter**:
- `id` = The worker ID.

**Response**:
```json
{
  "status": "stopped"
}
```
or
```json
{
  "status": "in_error_state"
}
```

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

---

### GET /api/youtube/auth
**Purpose**: Checks if a valid YouTube session cookie is set (to confirm authentication).  

**Response**:
```json
{
  "message": "Authenticated."
}
```
Returns `200 OK` if cookies are valid, otherwise `401` with `{ "message": "Not authenticated." }`.

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
  "allowedTypes": ["added", "completed", "error", "cancelled", "cleared", "log_info", "log_success", ...]
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
