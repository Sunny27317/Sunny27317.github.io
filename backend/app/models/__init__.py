# app/models/__init__.py
#
# DocLoop — model registry
#
# PURPOSE: Import every SQLAlchemy model here so that:
#   1. Alembic's env.py only needs to import this one module to
#      discover all table metadata for autogenerate.
#   2. Relationship back-populates resolve without import-order issues.
#   3. There is a single place to audit "what tables exist".
#
# RULE: When you add a new models/foo.py, add its import here.
# Keep imports grouped by domain for readability.

from app.models.base import Base  # noqa: F401  — Base must be first

# ------------------------------------------------------------------
# Core / auth
# ------------------------------------------------------------------
# from app.models.firm import Firm          # noqa: F401
# from app.models.user import User          # noqa: F401

# ------------------------------------------------------------------
# Clients
# ------------------------------------------------------------------
# from app.models.client import Client      # noqa: F401

# ------------------------------------------------------------------
# Workflow / cycles
# ------------------------------------------------------------------
# from app.models.workflow import WorkflowTemplate   # noqa: F401
# from app.models.cycle import Cycle                 # noqa: F401

# ------------------------------------------------------------------
# Documents
# ------------------------------------------------------------------
# from app.models.document import Document  # noqa: F401

# ------------------------------------------------------------------
# Async infrastructure (from schema patch)
# ------------------------------------------------------------------
# from app.models.background_job import BackgroundJob   # noqa: F401
# from app.models.notification import Notification      # noqa: F401
# from app.models.activity_log import ActivityLog       # noqa: F401

# ------------------------------------------------------------------
# Exported symbols
# ------------------------------------------------------------------
# Re-export Base so other modules can do:
#   from app.models import Base
# instead of drilling into app.models.base.
__all__ = ["Base"]
