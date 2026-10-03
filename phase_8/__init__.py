"""
Phase 8: Vercel Serverless Deployment & Configuration.
Provides serverless function adapters, cloud database migration scripts,
Vercel deployment manifests, environment validation, and deployment test runners.
"""

from phase_8.config import DeploymentConfig, get_deployment_config

__all__ = [
    "DeploymentConfig",
    "get_deployment_config",
]
