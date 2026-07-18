from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiohttp import web

from app.features.core.utils import api_error_response
from app.library.config import Config
from app.library.encoder import Encoder
from app.library.monitor import ResourceSample, ResourceTracker
from app.library.monitor_bottlenecks import detect as detect_bottlenecks
from app.library.router import route

if TYPE_CHECKING:
    from aiohttp.web import Request, Response, StreamResponse

KEEPALIVE = 15.0


def _disconnected(request: Request) -> bool:
    return request.transport is None or request.transport.is_closing()


def _parse_range(value: str) -> float | None:
    """Parse a range string like '5m', '1h', '30s' into seconds."""
    if not (value := value.strip().lower()):
        return None

    try:
        return float(value)
    except ValueError:
        pass

    multipliers: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for suffix, mult in multipliers.items():
        if value.endswith(suffix):
            try:
                return float(value[:-1]) * mult
            except ValueError:
                return None
    return None


@route("GET", "api/stats/latest", "stats.latest")
async def stats_latest(encoder: Encoder, config: Config) -> Response:
    if not config.monitor_enabled:
        return api_error_response(
            "Resource monitoring is disabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPForbidden.status_code,
            params={"feature": "api.features.monitoring"},
        )
    tracker: ResourceTracker = ResourceTracker.get_instance()
    if not (data := tracker.latest()):
        return web.json_response({}, dumps=encoder.encode)

    return web.json_response(data, dumps=encoder.encode)


@route("GET", "api/stats/history", "stats.history")
async def stats_history(request: Request, encoder: Encoder, config: Config) -> Response:
    if not config.monitor_enabled:
        return api_error_response(
            "Resource monitoring is disabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPForbidden.status_code,
            params={"feature": "api.features.monitoring"},
        )

    range_str: str = request.query.get("range", "30m")
    range_s: float | None = _parse_range(range_str)

    tracker: ResourceTracker = ResourceTracker.get_instance()
    return web.json_response(tracker.snapshot(range_seconds=range_s), dumps=encoder.encode)


@route("GET", "api/stats/bottlenecks", "stats.bottlenecks")
async def stats_bottlenecks(encoder: Encoder, config: Config) -> Response:
    if not config.monitor_enabled:
        return api_error_response(
            "Resource monitoring is disabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPForbidden.status_code,
            params={"feature": "api.features.monitoring"},
        )

    tracker: ResourceTracker = ResourceTracker.get_instance()
    history: list[dict[str, Any]] = tracker.snapshot(range_seconds=300)
    return web.json_response(detect_bottlenecks(history), dumps=encoder.encode)


@route("GET", "api/stats/stream", "stats.stream")
async def stats_stream(request: Request, encoder: Encoder, config: Config) -> StreamResponse | Response:
    if not config.monitor_enabled:
        return api_error_response(
            "Resource monitoring is disabled.",
            code="FEATURE_DISABLED",
            status=web.HTTPForbidden.status_code,
            params={"feature": "api.features.monitoring"},
        )

    tracker: ResourceTracker = ResourceTracker.get_instance()
    queue: asyncio.Queue[ResourceSample | None] = tracker.subscribe()

    response = web.StreamResponse(
        status=web.HTTPOk.status_code,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

    await response.prepare(request)

    async def _emit_raw(payload: str) -> bool:
        if _disconnected(request):
            return False
        try:
            await response.write(payload.encode("utf-8"))
        except ConnectionResetError:
            return False
        return True

    async def _emit_event(event: str, data: str) -> bool:
        return await _emit_raw(f"event: {event}\ndata: {data}\n\n")

    async def _keepalive() -> bool:
        return await _emit_raw(": keepalive\n\n")

    latest: dict[str, Any] = tracker.latest()
    if latest:
        await _emit_event("sample", encoder.encode(latest))

    from collections import deque

    history_window: deque[dict[str, Any]] = deque(maxlen=30)
    if latest:
        history_window.append(latest)

    last_bottlenecks: str | None = None

    try:
        while True:
            if _disconnected(request):
                break
            try:
                sample: ResourceSample | None = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE)
            except TimeoutError:
                if not await _keepalive():
                    break
                continue

            if sample is None:
                break

            sample_dict: dict[str, Any] = sample.to_dict()
            if not await _emit_event("sample", encoder.encode(sample_dict)):
                break

            # Update bottleneck window and check for changes.
            history_window.append(sample_dict)
            if len(history_window) >= 30:
                result: dict[str, Any] = detect_bottlenecks(list(history_window))
                encoded: str = encoder.encode(result)
                if encoded != last_bottlenecks:
                    last_bottlenecks = encoded
                    if not await _emit_event("bottleneck", encoded):
                        break
    except asyncio.CancelledError:
        pass
    finally:
        tracker.unsubscribe(queue)
        try:
            await response.write_eof()
        except ConnectionResetError:
            pass

    return response
