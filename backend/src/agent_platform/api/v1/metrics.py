"""Prometheus metrics middleware and /metrics endpoint.

Exposes request counts, latencies, and application-level gauges in
Prometheus text exposition format.  Zero external dependencies – uses
only the stdlib so the image stays slim.
"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter()

# ---- In-process counters (thread-safe via GIL) ----

_request_count: dict[str, int] = defaultdict(int)
_request_latency_sum: dict[str, float] = defaultdict(float)
_request_latency_count: dict[str, int] = defaultdict(int)
_error_count: dict[str, int] = defaultdict(int)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Collect per-route request count & latency."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path

        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        label = f'{method}|{path}|{response.status_code}'
        _request_count[label] += 1
        _request_latency_sum[label] += elapsed
        _request_latency_count[label] += 1

        if response.status_code >= 500:
            _error_count[f'{method}|{path}'] += 1

        return response


def _render_metrics() -> str:
    """Render all metrics in Prometheus text exposition format."""
    lines: list[str] = []

    # request_total
    lines.append("# HELP forge_http_requests_total Total HTTP requests")
    lines.append("# TYPE forge_http_requests_total counter")
    for label, count in sorted(_request_count.items()):
        method, path, status = label.split("|", 2)
        lines.append(
            f'forge_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    # request_duration_seconds
    lines.append("# HELP forge_http_request_duration_seconds Request latency in seconds")
    lines.append("# TYPE forge_http_request_duration_seconds summary")
    for label, total in sorted(_request_latency_sum.items()):
        method, path, status = label.split("|", 2)
        cnt = _request_latency_count[label]
        lines.append(
            f'forge_http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.6f}'
        )
        lines.append(
            f'forge_http_request_duration_seconds_count{{method="{method}",path="{path}",status="{status}"}} {cnt}'
        )

    # errors
    lines.append("# HELP forge_http_errors_total Total 5xx errors")
    lines.append("# TYPE forge_http_errors_total counter")
    for label, count in sorted(_error_count.items()):
        method, path = label.split("|", 1)
        lines.append(
            f'forge_http_errors_total{{method="{method}",path="{path}"}} {count}'
        )

    lines.append("")
    return "\n".join(lines)


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=_render_metrics(), media_type="text/plain; charset=utf-8")
