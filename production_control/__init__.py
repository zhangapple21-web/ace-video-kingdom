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
from .projection import prepare_model_request, project_messages
from .image_assets import AssetStore, InlineImageError, VisionAnalysisCache, assert_model_boundary, build_frame_analysis_plan, ingest_ui_image, sample_frame_indices
from .model_transport import build_chat_payload, build_responses_payload, materialize_provider_messages, post_chat_completion, post_responses

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
    "prepare_model_request",
    "AssetStore",
    "InlineImageError",
    "VisionAnalysisCache",
    "assert_model_boundary",
    "build_frame_analysis_plan",
    "ingest_ui_image",
    "sample_frame_indices",
    "build_chat_payload",
    "build_responses_payload",
    "materialize_provider_messages",
    "post_chat_completion",
    "post_responses",
]
