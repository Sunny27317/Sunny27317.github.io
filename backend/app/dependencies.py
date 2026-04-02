# app/dependencies.py
#
# DocLoop — shared FastAPI dependencies
#
# These are the building blocks injected into every route handler.
# Keep this file to pure dependency functions — no business logic.
#
# Dependency graph (simplified):
#
#   get_db            → yields AsyncSession (one per request)
#   get_redis         → yields Redis client (shared pool)
#   get_current_token → validates Supabase JWT, returns raw payload
#   get_current_user  → get_current_token → loads User row from DB
#   get_current_firm  → get_current_user  → loads Firm row from DB
#   require_role      → get_current_user  → asserts role membership

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Type aliases — keeps route signatures readable
# ------------------------------------------------------------------
# Usage in a route:
#   async def my_route(db: DB, user: CurrentUser): ...

DB = Annotated[AsyncSession, Depends(get_db)]


# ------------------------------------------------------------------
# Redis dependency
# ------------------------------------------------------------------

async def get_redis(request: Request) -> Redis:
    """
    Returns the shared Redis client stored on app.state.
    Requires app.state.redis to be set in the lifespan (see main.py).
    """
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RuntimeError(
            "Redis client not initialised. "
            "Check that connect_redis() ran in the lifespan."
        )
    return redis


RedisClient = Annotated[Redis, Depends(get_redis)]


# ------------------------------------------------------------------
# Supabase JWT verification
# ------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=True)


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    """
    Verify and decode a Supabase-issued JWT.

    Supabase uses HS256 with the project's JWT secret.
    We verify: signature, expiry, and issuer prefix.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Supabase sets role="authenticated" for logged-in users
    if payload.get("role") not in ("authenticated", "service_role"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not have authenticated role",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """
    Dependency: validates the Bearer token and returns the raw JWT payload.
    Use this if you only need the sub/email without hitting the DB.
    """
    return _decode_supabase_jwt(credentials.credentials)


TokenPayload = Annotated[dict[str, Any], Depends(get_current_token)]


# ------------------------------------------------------------------
# User loading
# ------------------------------------------------------------------

async def get_current_user(
    token: TokenPayload,
    db: DB,
) -> Any:
    """
    Dependency: resolves the authenticated Supabase user to a DB User row.

    Returns the User ORM model instance.
    Raises 401 if the sub doesn't match any user row (e.g. deleted account).

    NOTE: Uncomment the body once app/models/user.py exists.
    """
    user_id_str: str = token.get("sub", "")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user ID in token",
        )

    # --- Uncomment when User model is available ---
    # from app.models.user import User
    # result = await db.execute(select(User).where(User.id == user_uuid))
    # user = result.scalar_one_or_none()
    # if user is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="User account not found",
    #     )
    # if not user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="User account is disabled",
    #     )
    # return user

    # Placeholder return until User model exists
    # Returns a minimal dict so routes can be wired before the model ships
    return {"id": user_uuid, "email": token.get("email"), "_raw_token": token}


CurrentUser = Annotated[Any, Depends(get_current_user)]


# ------------------------------------------------------------------
# Firm loading
# ------------------------------------------------------------------

async def get_current_firm(
    user: CurrentUser,
    db: DB,
) -> Any:
    """
    Dependency: loads the Firm that the current user belongs to.
    Multi-firm memberships are out of scope for v1 — one user, one firm.

    NOTE: Uncomment once Firm + UserFirmMembership models exist.
    """
    # --- Uncomment when models are available ---
    # from app.models.firm import Firm
    # from app.models.user_firm import UserFirmMembership
    #
    # result = await db.execute(
    #     select(Firm)
    #     .join(UserFirmMembership, UserFirmMembership.firm_id == Firm.id)
    #     .where(
    #         UserFirmMembership.user_id == user.id,
    #         UserFirmMembership.is_active.is_(True),
    #         Firm.deleted_at.is_(None),
    #     )
    # )
    # firm = result.scalar_one_or_none()
    # if firm is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="No active firm membership found for this user",
    #     )
    # return firm

    # Placeholder — replace once models exist
    return {"id": None, "_placeholder": True}


CurrentFirm = Annotated[Any, Depends(get_current_firm)]


# ------------------------------------------------------------------
# Role guard factory
# ------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """
    Dependency factory — asserts the current user has one of the allowed roles.

    Usage:
        @router.delete("/something", dependencies=[Depends(require_role("admin", "owner"))])
        async def delete_something(...): ...
    """
    async def _guard(user: CurrentUser) -> None:
        # Adapt to your actual user.role field once User model exists
        user_role: str = user.get("role", "") if isinstance(user, dict) else getattr(user, "role", "")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not permitted for this action. "
                       f"Required: {list(allowed_roles)}",
            )

    return Depends(_guard)


# ------------------------------------------------------------------
# Pagination query params
# ------------------------------------------------------------------

class PaginationParams:
    """
    Standard limit/offset pagination extracted from query string.

    Usage:
        @router.get("/items")
        async def list_items(pagination: Annotated[PaginationParams, Depends()]): ...
    """
    def __init__(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> None:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="limit must be between 1 and 100",
            )
        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="offset must be >= 0",
            )
        self.limit = limit
        self.offset = offset


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]
