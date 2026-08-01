"""
BharatHealth Analyst — API middleware
Rate limiting and request logging for the FastAPI backend.
"""

import json
import time
from collections import defaultdict, deque
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

ROOT = Path(__file__).parent.parent.parent
LOG_PATH = ROOT / "backend" / "api" / "logs" / "requests.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Endpoints exempt from rate limiting (cheap, or needed for docs/browsing)
EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
EXEMPT_PREFIXES = ("/charts",)

FREE_LIMIT_PER_MIN = 10
AUTH_LIMIT_PER_MIN = 100
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window limiter. Fine for a single-instance demo deploy —
    would need a shared store (e.g. Redis) behind multiple workers/instances."""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("x-api-key")
        client_ip = request.client.host if request.client else "unknown"
        client_id = api_key or client_ip
        limit = AUTH_LIMIT_PER_MIN if api_key else FREE_LIMIT_PER_MIN

        now = time.time()
        hits = self._hits[client_id]
        while hits and hits[0] < now - WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: {limit} requests/minute. "
                              f"Pass an X-API-Key header for a higher limit, or try again shortly."
                },
            )

        hits.append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Appends one JSON line per request to backend/api/logs/requests.jsonl.

    Local stand-in for the blueprint's Cloud Logging/BigQuery usage analytics —
    swap this for a BigQuery client once real GCP credentials are available.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        latency_ms = round((time.time() - start) * 1000, 1)

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "client_ip": request.client.host if request.client else None,
        }
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # logging must never break the request

        return response
