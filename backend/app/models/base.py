# app/models/base.py
#
# DocLoop — SQLAlchemy declarative base + shared column mixins
# Every model in the project inherits from Base.
# Mixins are opt-in — include only what a table actually needs.

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ------------------------------------------------------------------
# Declarative base
# ------------------------------------------------------------------

class Base(DeclarativeBase):
    """
    Project-wide declarative base.
    All models must inherit from this class so Alembic's autogenerate
    can discover them via app/models/__init__.py imports.
    """
    pass


# ------------------------------------------------------------------
# Reusable mixins
# ------------------------------------------------------------------

class UUIDPrimaryKeyMixin:
    """
    UUID v4 primary key, server-generated as a default.
    Prefer gen_random_uuid() over uuid_generate_v4() — available in
    Postgres 13+ without the uuid-ossp extension.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    """
    created_at is set once on INSERT by the DB server.
    updated_at is refreshed on every UPDATE by the DB server.
    Using server-side defaults means the values are always reliable
    even if the row is modified outside of SQLAlchemy (migrations,
    Supabase Studio, scripts).
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    """
    Soft-delete support. Rows are never physically deleted;
    instead deleted_at is stamped and all queries filter WHERE deleted_at IS NULL.

    Use the `is_deleted` property for in-Python checks.
    See app/repositories/base.py for query helpers that auto-apply the filter.
    """
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        default=None,
    )
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deletion_reason: Mapped[str | None] = mapped_column(nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, by_user_id: uuid.UUID, reason: str | None = None) -> None:
        """Stamp the deletion — caller must still commit the session."""
        self.deleted_at = datetime.now(tz=timezone.utc)
        self.deleted_by_id = by_user_id
        self.deletion_reason = reason


class FirmScopedMixin:
    """
    Every multi-tenant entity belongs to exactly one firm.
    This mixin enforces the FK at the model level so it can never
    be accidentally omitted on a new model.
    """
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
