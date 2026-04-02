# app/utils/exceptions.py
#
# DocLoop — domain exception hierarchy
#
# Service-layer code raises these typed exceptions.
# Route handlers catch them and convert to HTTP responses.
# This keeps HTTP concerns out of the service layer entirely.
#
# Pattern in a route handler:
#
#   from app.utils.exceptions import NotFoundError, ForbiddenError
#
#   @router.get("/clients/{id}")
#   async def get_client(id: UUID, user: CurrentUser, db: DB):
#       try:
#           return ok(await client_service.get(db, id, firm_id=user.firm_id))
#       except NotFoundError as exc:
#           raise HTTPException(status_code=404, detail=str(exc))
#       except ForbiddenError as exc:
#           raise HTTPException(status_code=403, detail=str(exc))

from __future__ import annotations


class DocLoopError(Exception):
    """Base class for all application exceptions."""
    pass


class NotFoundError(DocLoopError):
    """Resource does not exist or is not visible to the current user."""
    pass


class ForbiddenError(DocLoopError):
    """User is authenticated but not authorised for this action."""
    pass


class ConflictError(DocLoopError):
    """Operation conflicts with existing state (e.g. duplicate email)."""
    pass


class ValidationError(DocLoopError):
    """Business-rule validation failure (distinct from Pydantic schema validation)."""
    pass


class ExternalServiceError(DocLoopError):
    """A third-party service (Resend, Twilio, Stripe, OpenAI) returned an error."""
    def __init__(self, service: str, message: str) -> None:
        self.service = service
        super().__init__(f"{service}: {message}")


class JobError(DocLoopError):
    """Background job failed to enqueue or execute."""
    pass


class StorageError(DocLoopError):
    """Supabase Storage upload/download failed."""
    pass
