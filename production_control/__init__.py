"""Industrial, fail-closed video production control plane.

The package is intentionally provider-agnostic.  It coordinates local
artifacts, evidence and release gates; it never submits work to a provider.
"""

from .engine import ProductionControl, WorkflowError
from .demand import (
    infer_goal,
    normalize_request,
    route,
    infer_task_requirements,
    route_model_demand,
    load_provider_health_snapshot,
    select_fallback_labor,
)
from .workflow import preflight_plan
from .media_routing import classify_media_intent, route_media_demand
from .media_executor import execute_media_task
from .project import discover_project, manifest_hash
from .projection import project_messages

__all__ = [
    "ProductionControl",
    "WorkflowError",
    "infer_goal",
    "normalize_request",
    "route",
    "infer_task_requirements",
    "route_model_demand",
    "load_provider_health_snapshot",
    "select_fallback_labor",
    "preflight_plan",
    "classify_media_intent",
    "route_media_demand",
    "execute_media_task",
    "discover_project",
    "manifest_hash",
    "project_messages",
]
