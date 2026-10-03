"""
Phase 6: Interactive Web UI & API Layer.
"""
from phase_6.api import (
    RecommendationRequest,
    handle_health_endpoint,
    handle_metadata_endpoint,
    handle_recommendations_endpoint,
)
from phase_6.server import ThreadedHTTPServer, create_server, run_server

__all__ = [
    "RecommendationRequest",
    "handle_recommendations_endpoint",
    "handle_health_endpoint",
    "handle_metadata_endpoint",
    "ThreadedHTTPServer",
    "create_server",
    "run_server",
]
