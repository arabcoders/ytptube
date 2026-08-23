# Generic Task Definitions

Generic Task Definitions tell YTPTube how to discover download URLs from a site that does not have a suitable built-in
handler, RSS feed, or API integration.

A **definition** is a reusable fetch-and-parse recipe. A **Task** supplies the URL, schedule, Preset, archive settings,
and queue policy that use that recipe. The definition discovers items; the Task decides when and how they are downloaded.

The [Task Definition schema](../app/schema/task_definition.json) is the authoritative validation contract.

> [!IMPORTANT]
>
> Before creating a definition, test one final item URL directly with yt-dlp. A Generic Task Definition discovers URLs;
> it does not add an extractor to yt-dlp. If yt-dlp cannot download the discovered media or page URL on its own, the
> definition will not make it downloadable.

## Create and test a definition

1. Open **Tasks > Definitions**.
2. Create a definition in the visual editor or paste JSON into **Advanced**.
3. Test the definition with a concrete URL before saving it.
4. Create a Task whose URL matches one of the definition's `match_url` patterns.
5. Give the Task a Preset with a download archive so later runs can skip known items.

Use **Actions > Test** to test a saved definition. The editor's **Test** action tests an unsaved copy and leaves the
editor open.

## Minimal definition

```json
{
  "name": "Example articles",
  "match_url": ["https://example.com/articles/*"],
  "definition": {
    "parse": {
      "url": {
        "type": "css",
        "expression": "article a",
        "attribute": "href"
      }
    }
  }
}
```

`name`, a non-empty `match_url` array, and `definition.parse` are required. A direct parser requires `parse.url`. A
container parser requires `parse.items.fields.url`.

The API generates `id`, `created_at`, and `updated_at`; omit them when creating or updating a definition.

## Matching Task URLs

`match_url` accepts one or more glob or regular-expression strings. YTPTube checks enabled definitions in ascending
`priority` order, then by name, and uses the first definition that matches the Task URL.

Glob example:

```json
{
  "match_url": ["https://example.com/articles/*"]
}
```

Regular expressions must be enclosed by `/` characters:

```json
{
  "match_url": ["/https:\/\/example\\.com\/post\/[0-9]+/"]
}
```

`priority` is a non-negative integer and defaults to `0`. Lower numbers run first. `enabled` defaults to `true`; disabled
definitions are ignored. Avoid broad overlapping patterns unless their priorities make the intended selection clear.

## Fetch Engines

### HTTP

The default engine uses YTPTube's shared HTTP transport. The engine can select a curl-cffi browser identity, include its
default headers, or opt into the configured FlareSolverr-compatible service:

```json
{
  "engine": {
    "type": "http",
    "options": {
      "impersonate": "chrome",
      "curl_default_headers": true,
      "flaresolverr": false
    }
  }
}
```

The proxy comes from the Task's yt-dlp options, not from the definition document.

### Browser

Use the browser engine when the page must run JavaScript before its items appear. YTPTube connects to an existing remote
Chromium instance over CDP; it does not start a browser for the definition.

```json
{
  "engine": {
    "type": "browser",
    "options": {
      "protocol": "cdp",
      "url": "http://browser:9222",
      "wait_for": {
        "type": "css",
        "expression": ".cards"
      },
      "wait_timeout": 15,
      "page_load_timeout": 60
    }
  }
}
```

`options.url` must be an absolute HTTP or HTTPS endpoint. `cdp` is the only supported protocol. `wait_for` accepts a CSS
or XPath expression. Both timeout values accept `0` through `300` seconds.

## Requests and Responses

The optional `request` object can:

- Override the Task URL with an absolute HTTP or HTTPS `url`.
- Select `GET` or `POST`.
- Add string-valued `headers`.
- Add string, number, boolean, or null query `params`.
- Set a request `timeout`.
- Send a `form`, `json`, or `raw` body with `POST`.

Example JSON request:

```json
{
  "request": {
    "method": "POST",
    "url": "https://example.com/api/search",
    "headers": {
      "Accept": "application/json"
    },
    "params": {
      "page": 1,
      "safe": true
    },
    "body": {
      "type": "json",
      "value": {
        "query": "new videos"
      }
    },
    "timeout": 30
  }
}
```

`response.type` is `html` by default. Set it to `json` when the response body is JSON:

```json
{
  "response": { "type": "json" }
}
```

## Parsing Modes

### Container parsing

Container parsing is recommended for repeated cards, rows, or JSON objects. `parse.items.selector` selects each item,
then every field is extracted within that item's scope. A missing field in one item does not shift values from another.

```json
{
  "parse": {
    "items": {
      "selector": ".cards .card",
      "fields": {
        "url": {
          "type": "css",
          "expression": "a",
          "attribute": "href"
        },
        "title": {
          "type": "css",
          "expression": "h2",
          "attribute": "text"
        }
      }
    }
  }
}
```

### Direct parsing

Direct parsing puts fields directly under `parse`. For HTML, each rule produces a list and values are paired by their
position in the `url` result. Use it only when independent selectors have a stable order. For JSON, direct parsing uses
the first value from each rule and produces at most one item.

```json
{
  "parse": {
    "url": {
      "type": "css",
      "expression": "article a",
      "attribute": "href"
    },
    "title": {
      "type": "css",
      "expression": "article h2",
      "attribute": "text"
    }
  }
}
```

Do not combine direct fields with `parse.items`.

## Extraction Rules

HTML responses support `css`, `xpath`, and `regex` rules:

- CSS and XPath rules select elements from the current page or container.
- `attribute: "text"` or `"inner_text"` returns normalized text.
- `attribute: "html"` or `"outer_html"` returns the HTML fragment.
- Any other `attribute` reads that element attribute.
- A `url` rule without `attribute` falls back to `href` when needed.
- Regex rules scan the current HTML scope. `attribute` can select a named or numbered capture group.
- `post_filter` applies a final regular expression to the extracted value.

JSON responses use rules with `type: "jsonpath"`, but their expressions are
[JMESPath](https://jmespath.org/) expressions:

```json
{
  "parse": {
    "items": {
      "type": "jsonpath",
      "selector": "results",
      "fields": {
        "url": { "type": "jsonpath", "expression": "url" },
        "title": { "type": "jsonpath", "expression": "title" },
        "channel": { "type": "jsonpath", "expression": "channel.name" }
      }
    }
  }
}
```

The recognized item fields are `url`, `title`, `thumbnail`, `description`, and `published`. Other fields become custom
metadata available to Conditions and downstream processing.

`archive_id` is generated internally and cannot be extracted by a definition.

## Inspection and Archive IDs

Inspection shows the matched definition, fetched items, extracted metadata, and archive state before the Task is run.
Saved and unsaved definitions can both be inspected against a concrete matching URL.

`resolve_ids` defaults to `true`. When an extracted item does not already have a cached archive ID, inspection can ask
yt-dlp to resolve one. Set `resolve_ids` to `false` through the inspection API when fast extraction matters more than ID
resolution.

Normal Task execution skips an item when its archive ID cannot be resolved. Inspection keeps unresolved items visible
with a null archive ID so the definition can be debugged.

See [`POST /api/tasks/definitions/inspect`](../API.md#post-apitasksdefinitionsinspect) for API usage.

## Visual and Advanced Editors

The visual editor covers common engine, request, response, container, and extraction settings. A document that uses
properties the visual editor cannot safely round-trip opens in **Advanced** mode. Advanced mode accepts the complete
definition document as JSON.

Export produces one definition with this envelope:

```json
{
  "_type": "task_definition",
  "_version": "2.0",
  "name": "Example articles",
  "priority": 0,
  "enabled": true,
  "match_url": ["https://example.com/articles/*"],
  "definition": {
    "parse": {
      "url": {
        "type": "css",
        "expression": "article a",
        "attribute": "href"
      }
    }
  }
}
```

Import requires `_version: "2.0"`. `_type`, when present, must be `task_definition`. The editor removes both envelope
fields before saving the document.

## Using AI to Create a Definition

Give the AI the target page, the fields you want, and the current
[Task Definition schema](../app/schema/task_definition.json). Do not ask it to guess from a description when it can
inspect representative HTML or JSON instead.

Example prompt:

> Create one YTPTube Generic Task Definition for `SITE_URL`. Follow `SCHEMA_URL` exactly. Determine whether the response
> is HTML or JSON and whether the HTTP engine or remote Chromium over CDP is required. Extract the item URL and, when
> available, title, thumbnail, description, and published date. Use container parsing for repeated items. Return only the
> definition document as JSON, without `id`, timestamps, `archive_id`, `_type`, or `_version`. Do not invent credentials,
> headers, selectors, or endpoints. I will paste the result into Advanced mode and test it before saving.

Replace `SITE_URL` and `SCHEMA_URL`, then paste the generated document into **Advanced**. Test it with a concrete URL and
inspect every discovered URL and metadata field before scheduling a Task. If using the Import action instead, add the
`_type` and `_version` envelope shown above.

Generated definitions are starting points. Selectors, endpoints, and site behavior change, and plausible generated rules
may still be wrong. Never send passwords, cookies, tokens, private headers, or private page content to an AI service.

## Common Validation Errors

- Missing `name`, `match_url`, or `definition.parse`.
- A direct parser without `url`.
- An `items` parser without `selector`, `fields`, or `fields.url`.
- Mixing `items` with direct parser fields.
- Using CSS or XPath rules for a JSON response.
- Using `jsonpath` rules for an HTML response.
- Sending a request body with `GET`.
- Using a relative request or browser endpoint URL.
- Using a browser protocol other than `cdp`.
- Extracting `archive_id`.
- Adding properties not defined by the schema.

## Complete Examples

### HTML cards with custom metadata

```json
{
  "name": "Example cards",
  "priority": 10,
  "enabled": true,
  "match_url": ["https://example.com/list/*"],
  "definition": {
    "parse": {
      "items": {
        "selector": ".card",
        "fields": {
          "url": { "type": "css", "expression": "a", "attribute": "href" },
          "title": { "type": "css", "expression": "h2", "attribute": "text" },
          "published": { "type": "css", "expression": "time", "attribute": "datetime" },
          "category": { "type": "css", "expression": ".category", "attribute": "text" }
        }
      }
    }
  }
}
```

### POST request with a JSON response

```json
{
  "name": "Example search",
  "match_url": ["https://example.com/search/*"],
  "definition": {
    "request": {
      "method": "POST",
      "url": "https://example.com/api/search",
      "body": { "type": "json", "value": { "page": 1 } }
    },
    "response": { "type": "json" },
    "parse": {
      "items": {
        "type": "jsonpath",
        "selector": "results",
        "fields": {
          "url": { "type": "jsonpath", "expression": "url" },
          "title": { "type": "jsonpath", "expression": "title" }
        }
      }
    }
  }
}
```

### Browser-rendered list

```json
{
  "name": "Example browser list",
  "match_url": ["https://example.com/dynamic/*"],
  "definition": {
    "engine": {
      "type": "browser",
      "options": {
        "protocol": "cdp",
        "url": "http://browser:9222",
        "wait_for": { "type": "css", "expression": ".cards" },
        "wait_timeout": 15,
        "page_load_timeout": 60
      }
    },
    "parse": {
      "items": {
        "selector": ".cards .card",
        "fields": {
          "url": { "type": "css", "expression": "a", "attribute": "href" },
          "title": { "type": "css", "expression": "h2", "attribute": "text" }
        }
      }
    }
  }
}
```
