"""
Deployment Configuration and Environment Variable Loader for Phase 8.
Reads configuration from environment variables and local .env files with zero external dependencies.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional


def load_env_file(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Parses key-value pairs from a .env file and injects them into os.environ if not already set.
    """
    if env_path is None:
        # Check root or local directory
        root_path = Path(__file__).resolve().parent.parent / ".env"
        local_path = Path(".env").resolve()
        phase8_path = Path(__file__).resolve().parent / ".env"

        for candidate in [root_path, local_path, phase8_path]:
            if candidate.is_file():
                env_path = candidate
                break

    loaded: Dict[str, str] = {}
    if not env_path or not env_path.is_file():
        return loaded

    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip wrapping single or double quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                loaded[key] = val
                if key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

    return loaded


# Automatically attempt to load on module import
_loaded_env = load_env_file()


class DeploymentConfig:
    """Encapsulates all deployment settings for Vercel Serverless environment."""

    def __init__(self):
        # Refresh loaded env
        load_env_file()

        # LLM Credentials
        self.gemini_api_key: Optional[str] = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or None
        )
        self.gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

        # Database Configuration
        self.database_url: Optional[str] = os.environ.get("DATABASE_URL")
        self.data_source: str = os.environ.get("RESTAURANT_DATA_SOURCE", "local_parquet")

        # Serverless Runtime Settings
        self.vercel_env: str = os.environ.get("VERCEL_ENV", "development")
        try:
            self.timeout_seconds: int = int(os.environ.get("SERVERLESS_TIMEOUT_SECONDS", "15"))
        except ValueError:
            self.timeout_seconds = 15

        self.enable_guardrails: bool = (
            os.environ.get("ENABLE_ANTI_HALLUCINATION_GUARDRAILS", "true").lower() in ("true", "1", "yes")
        )

        try:
            self.port: int = int(os.environ.get("PORT", "8000"))
        except ValueError:
            self.port = 8000
        self.host: str = os.environ.get("HOST", "127.0.0.1")

    @property
    def is_production(self) -> bool:
        return self.vercel_env.lower() == "production"

    @property
    def has_gemini_credentials(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here")

    @property
    def has_database_credentials(self) -> bool:
        return bool(
            self.database_url
            and "username:password" not in self.database_url
            and self.database_url.startswith("postgresql://")
        )

    def validate(self) -> Dict[str, Any]:
        """Runs pre-flight validation on the current environment configuration."""
        errors = []
        warnings = []

        if not self.has_gemini_credentials:
            warnings.append(
                "GEMINI_API_KEY is not set or using placeholder. System will use DeterministicMockProvider / TemplateFallbackProvider."
            )

        if self.data_source == "cloud_postgres" and not self.has_database_credentials:
            errors.append(
                "RESTAURANT_DATA_SOURCE is set to 'cloud_postgres' but DATABASE_URL is missing or invalid."
            )

        if self.timeout_seconds <= 0:
            errors.append(f"Invalid SERVERLESS_TIMEOUT_SECONDS: {self.timeout_seconds}")
        elif self.timeout_seconds > 30:
            warnings.append(
                f"SERVERLESS_TIMEOUT_SECONDS ({self.timeout_seconds}s) exceeds typical Vercel Hobby tier limit (15s)."
            )

        return {
            "status": "ready" if not errors else "configuration_error",
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "config_summary": {
                "vercel_env": self.vercel_env,
                "gemini_model": self.gemini_model,
                "has_gemini": self.has_gemini_credentials,
                "data_source": self.data_source,
                "has_database": self.has_database_credentials,
                "timeout_seconds": self.timeout_seconds,
            },
        }


def get_deployment_config() -> DeploymentConfig:
    """Singleton getter for DeploymentConfig."""
    return DeploymentConfig()
