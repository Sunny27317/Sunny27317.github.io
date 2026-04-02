# app/routers/health.py
#
# DocLoop — /health endpoint
#
# Used by:
#   - Docker / Railway / Render health checks
#   - Frontend "is the API up?" pre-flight
#   - Load balancer liveness probe
#
# Intentionally has NO auth dependency — it must respond even if
# the auth system is degraded.

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter(tags=["system"])

_start_time = time.time()


@router.get(
    "/health",
    summary="Health check",
    response_description="Service health status",
    status_code=status.HTTP_200_OK,
)
async def health_check(request: Request) -> JSONResponse:
    """
    Returns the health status of every critical dependency.

    Response shape:
    ```json
    {
      "status": "ok" | "degraded",
      "version": "0.1.0",
      "uptime_seconds": 123,
      "checks": {
        "database": "ok" | "error",
        "redis":    "ok" | "error" | "unavailable",
      }
    }
    ```

    HTTP 200 if all checks pass.
    HTTP 503 if any critical check fails (database).
    Redis failure is non-critical — status becomes "degraded" but HTTP is still 200.
    """
    checks: dict[str, Any] = {}
    overall_ok = True

    # ── Database check ──
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        overall_ok = False  # DB failure = critical

    # ── Redis check ──
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        checks["redis"] = "unavailable"
    else:
        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            # Redis failure = degraded (non-critical for read paths)

    # ── APScheduler check ──
    scheduler = getattr(request.app.state, "scheduler", None)
    checks["scheduler"] = "ok" if (scheduler and scheduler.running) else "stopped"

    payload = {
        "status": "ok" if overall_ok else "degraded",
        "version": request.app.version,
        "uptime_seconds": round(time.time() - _start_time),
        "checks": checks,
    }

    http_status = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=http_status)
