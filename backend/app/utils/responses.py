# app/utils/responses.py
#
# DocLoop — canonical API response helpers
#
# Every successful route returns through one of these helpers so the
# frontend lib/api.ts always sees a consistent envelope:
#
#   Success:  { "success": true,  "data": <payload>,  "meta": <optional> }
#   Error:    { "success": false, "error": { "message": "...", "detail": ... } }
#
# Error responses are handled by exception handlers in main.py.
# These helpers are for success responses only.

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


# ------------------------------------------------------------------
# Success envelope
# ------------------------------------------------------------------

def ok(
    data: Any = None,
    *,
    status_code: int = status.HTTP_200_OK,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    """
    Standard success response.

    Args:
        data:        The payload. Can be any JSON-serialisable value.
        status_code: Override for 201, 202, etc.
        meta:        Optional metadata (pagination, totals, etc.)

    Shape:
        { "success": true, "data": ..., "meta": ... }
    """
    body: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        body["meta"] = meta
    return JSONResponse(status_code=status_code, content=body)


def created(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    """Convenience wrapper for HTTP 201 Created."""
    return ok(data, status_code=status.HTTP_201_CREATED, meta=meta)


def accepted(data: Any = None, meta: dict[str, Any] | None = None) -> JSONResponse:
    """Convenience wrapper for HTTP 202 Accepted (async job enqueued)."""
    return ok(data, status_code=status.HTTP_202_ACCEPTED, meta=meta)


def no_content() -> JSONResponse:
    """HTTP 204 — used for DELETE responses."""
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


# ------------------------------------------------------------------
# Paginated list helper
# ------------------------------------------------------------------

def paginated(
    items: list[Any],
    *,
    total: int,
    limit: int,
    offset: int,
) -> JSONResponse:
    """
    Wraps a list result with pagination metadata.

    Shape:
        {
          "success": true,
          "data": [...],
          "meta": { "total": 120, "limit": 20, "offset": 0, "has_more": true }
        }
    """
    return ok(
        data=items,
        meta={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        },
    )


# ------------------------------------------------------------------
# Job-enqueued helper
# ------------------------------------------------------------------

def job_accepted(job_id: str, job_type: str) -> JSONResponse:
    """
    Used by routes that kick off an async background job.
    The frontend polls GET /api/v1/jobs/{job_id} for status.

    Shape:
        {
          "success": true,
          "data": { "job_id": "...", "job_type": "zip_export", "status": "pending" }
        }
    """
    return accepted(
        data={"job_id": job_id, "job_type": job_type, "status": "pending"}
    )
