# app/main.py
#
# DocLoop — FastAPI application entrypoint
#
# Startup order:
#   1. Database connection pool warmed up
#   2. Redis connected
#   3. APScheduler started
#   4. ARQ worker pool referenced (ARQ workers run as separate processes)
#
# Shutdown order (reverse):
#   4. APScheduler stopped
#   3. Redis connection closed
#   2. DB pool disposed
#
# All routers are registered in _register_routers().
# Add new domain routers there — main.py itself never grows long.

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import connect_db, disconnect_db

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Logging — configure once at module level
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


# ------------------------------------------------------------------
# Lifespan — startup / shutdown
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Everything before `yield` runs at startup.
    Everything after `yield` runs at shutdown.
    app.state is the correct place to store shared resources.
    """
    logger.info("── DocLoop API starting up (env=%s) ──", settings.ENV)

    # 1. Database
    await connect_db()

    # 2. Redis
    redis_client = aioredis.from_url(
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
        await redis_client.ping()
        logger.info("✓ Redis connection established")
    except Exception as exc:
        logger.warning("✗ Redis ping failed (%s) — continuing without cache", exc)
    app.state.redis = redis_client

    # 3. APScheduler
    scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
    _register_scheduled_jobs(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("✓ APScheduler started (%d jobs)", len(scheduler.get_jobs()))

    # 4. ARQ — workers run as separate processes (`arq app.workers.WorkerSettings`)
    #    Nothing to start here; we just store the Redis settings reference
    #    so service-layer code can enqueue jobs via arq.create_pool().
    app.state.arq_redis_settings = settings.redis_arq_url
    logger.info("✓ ARQ queue target: %s", settings.redis_arq_url)

    logger.info("── DocLoop API ready ──")
    yield

    # ── Shutdown ──
    logger.info("── DocLoop API shutting down ──")

    scheduler.shutdown(wait=False)
    logger.info("✓ APScheduler stopped")

    await redis_client.aclose()
    logger.info("✓ Redis connection closed")

    await disconnect_db()
    logger.info("── DocLoop API shutdown complete ──")


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="DocLoop backend API — document workflow automation for accounting firms.",
        docs_url="/docs" if settings.ENV != "production" else None,
        redoc_url="/redoc" if settings.ENV != "production" else None,
        openapi_url="/openapi.json" if settings.ENV != "production" else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


# ------------------------------------------------------------------
# Middleware
# ------------------------------------------------------------------

def _register_middleware(app: FastAPI) -> None:
    # CORS — must be registered before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,           # needed for cookie-based auth flows
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],  # let frontend read request IDs
    )

    # Request timing — adds X-Process-Time header to every response
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        return response

    # Request ID propagation — reads X-Request-ID from frontend or generates one
    @app.middleware("http")
    async def propagate_request_id(request: Request, call_next):
        import uuid as _uuid
        req_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


# ------------------------------------------------------------------
# Exception handlers
# ------------------------------------------------------------------

def _api_error(status_code: int, message: str, detail: Any = None) -> JSONResponse:
    """
    Canonical error envelope used by all exception handlers.
    Shape:
        { "success": false, "error": { "message": "...", "detail": ... } }

    This matches the error shape the frontend lib/api.ts expects.
    """
    body: dict[str, Any] = {
        "success": False,
        "error": {"message": message},
    }
    if detail is not None:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def _register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """
        Pydantic validation errors → 422 with field-level details.
        The frontend can iterate exc.errors() to show per-field messages.
        """
        errors = [
            {
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        return _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Validation failed",
            detail=errors,
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return _api_error(status.HTTP_404_NOT_FOUND, "Resource not found")

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc):
        return _api_error(status.HTTP_405_METHOD_NOT_ALLOWED, "Method not allowed")

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return _api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred",
            detail=str(exc) if settings.DEBUG else None,
        )


# ------------------------------------------------------------------
# Router registration
# ------------------------------------------------------------------

def _register_routers(app: FastAPI) -> None:
    """
    Central router manifest.
    All routers share the /api/v1 prefix.
    Add new domain routers here as they are built — nowhere else.
    """
    from app.routers.health import router as health_router

    # ── Always-on system routes ──
    app.include_router(health_router)               # /health (no prefix)

    # ── API v1 routes (uncomment as routers are built) ──
    API_PREFIX = "/api/v1"

    # from app.routers.auth import router as auth_router
    # app.include_router(auth_router, prefix=API_PREFIX)

    # from app.routers.firms import router as firms_router
    # app.include_router(firms_router, prefix=API_PREFIX)

    # from app.routers.users import router as users_router
    # app.include_router(users_router, prefix=API_PREFIX)

    # from app.routers.clients import router as clients_router
    # app.include_router(clients_router, prefix=API_PREFIX)

    # from app.routers.documents import router as documents_router
    # app.include_router(documents_router, prefix=API_PREFIX)

    # from app.routers.cycles import router as cycles_router
    # app.include_router(cycles_router, prefix=API_PREFIX)

    # from app.routers.workflow import router as workflow_router
    # app.include_router(workflow_router, prefix=API_PREFIX)

    # from app.routers.automations import router as automations_router
    # app.include_router(automations_router, prefix=API_PREFIX)

    # from app.routers.analytics import router as analytics_router
    # app.include_router(analytics_router, prefix=API_PREFIX)

    # from app.routers.notifications import router as notifications_router
    # app.include_router(notifications_router, prefix=API_PREFIX)

    # from app.routers.jobs import router as jobs_router
    # app.include_router(jobs_router, prefix=API_PREFIX)

    # from app.routers.portal import router as portal_router
    # app.include_router(portal_router, prefix=API_PREFIX)

    # from app.routers.webhooks import router as webhooks_router
    # app.include_router(webhooks_router, prefix=API_PREFIX)


# ------------------------------------------------------------------
# APScheduler job registration
# ------------------------------------------------------------------

def _register_scheduled_jobs(scheduler: AsyncIOScheduler) -> None:
    """
    Register recurring background jobs.
    Each job should be a thin wrapper that delegates to a service function.
    Uncomment as services are built.
    """
    # from app.services.jobs import purge_expired_jobs
    # scheduler.add_job(
    #     purge_expired_jobs,
    #     trigger="cron",
    #     hour=3,
    #     minute=0,
    #     id="purge_expired_jobs",
    #     replace_existing=True,
    # )

    # from app.services.cycles import check_cycle_deadlines
    # scheduler.add_job(
    #     check_cycle_deadlines,
    #     trigger="interval",
    #     minutes=30,
    #     id="check_cycle_deadlines",
    #     replace_existing=True,
    # )
    pass


# ------------------------------------------------------------------
# Application instance
# ------------------------------------------------------------------

app = create_app()
