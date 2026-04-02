# app/database.py
#
# DocLoop — async database layer
# SQLAlchemy 2.x with asyncpg driver.
# Session lifecycle is managed per-request via FastAPI dependencies.
# The engine is created once at startup and closed at shutdown.

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------
# NullPool is used in test / serverless environments where connection
# pooling is handled externally (e.g. PgBouncer on Supabase).
# For a persistent server process, AsyncAdaptedQueuePool (the default)
# is correct — just don't pass poolclass here.
# ------------------------------------------------------------------

def _build_engine() -> AsyncEngine:
    kwargs: dict = {
        "echo": settings.DEBUG,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": True,       # detect stale connections before use
    }

    # asyncpg doesn't support statement_cache_size when used behind
    # PgBouncer in transaction mode — set to 0 to be safe.
    connect_args = {
        "statement_cache_size": 0,
        "server_settings": {
            "application_name": "docloop_api",
        },
    }

    return create_async_engine(
        str(settings.DATABASE_URL),
        connect_args=connect_args,
        **kwargs,
    )


engine: AsyncEngine = _build_engine()

# ------------------------------------------------------------------
# Session factory
# ------------------------------------------------------------------
# expire_on_commit=False is important for async: after commit, accessing
# attributes would trigger lazy loads which are not allowed in async.
# ------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------
# Request-scoped session — used by FastAPI dependency
# ------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a per-request AsyncSession.
    The session is always closed after the request, even on error.
    Commit/rollback is the caller's responsibility (service layer).

    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ------------------------------------------------------------------
# Transactional context manager for service-layer use
# ------------------------------------------------------------------

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Use inside background tasks / ARQ workers where you can't use
    FastAPI's dependency injection system.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
            await db.commit()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ------------------------------------------------------------------
# Lifecycle helpers — called from app lifespan
# ------------------------------------------------------------------

async def connect_db() -> None:
    """Validate DB connectivity at startup. Fails fast on misconfiguration."""
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("✓ Database connection established")
    except Exception as exc:
        logger.critical("✗ Database connection failed: %s", exc)
        raise


async def disconnect_db() -> None:
    """Dispose of the connection pool gracefully at shutdown."""
    await engine.dispose()
    logger.info("✓ Database connection pool closed")
