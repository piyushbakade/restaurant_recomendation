"""
Configuration settings for Phase 5: LLM Recommendation & Anti-Hallucination Guardrails.
"""
import os
from pathlib import Path

# Paths
PHASE_5_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_5_DIR.parent

# Automatically load .env if present
def _load_dotenv():
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    if k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_dotenv()

# Model configuration
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
API_KEY_ENV_VARS = ["GEMINI_API_KEY", "GOOGLE_API_KEY"]

# Generation hyperparameters (low temperature for strictly grounded outputs)
DEFAULT_TEMPERATURE = 0.2
MAX_OUTPUT_TOKENS = 1024
REQUEST_TIMEOUT_SECONDS = 15

# LLM Prompting & Guardrail Settings
MAX_CANDIDATES_FOR_LLM = 5
ENABLE_ANTI_HALLUCINATION_GUARDRAILS = True
MAX_REASONING_SENTENCES = 3

# Fallback Mode Settings
# If True and API key is missing or call fails, gracefully fallback to template-based synthesizer
ENABLE_TEMPLATE_FALLBACK_ON_ERROR = True
