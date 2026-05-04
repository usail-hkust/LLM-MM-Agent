"""
Jinja2 Template Engine configuration.
"""
import json
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings

logger = logging.getLogger(__name__)


def _to_json(value, **kwargs):
    """JSON filter for templates."""
    return json.dumps(value, ensure_ascii=False, default=str, **kwargs)


def _tex_safe(value):
    """Simple LaTeX escaping filter."""
    if not isinstance(value, str):
        return value
    return value.replace("_", r"\_").replace("%", r"\%").replace("$", r"\$").replace("#", r"\#")


# Initialize Environment lazily or at module level
# We assume templates are physically located at settings.TEMPLATE_ROOT
# Resolve path relative to backend/ directory
# Get backend directory (parent of app/)
backend_dir = Path(__file__).resolve().parent.parent.parent
template_path = backend_dir / settings.TEMPLATE_ROOT

if not template_path.exists():
    # Fallback or warning for dev environment setup
    logger.warning(f"Template directory {template_path} does not exist. Please create it.")
    # Create minimal structure if missing
    template_path.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(
    loader=FileSystemLoader(str(template_path)),
    # [CRITICAL FIX] 
    # Removed 'j2' from autoescape list.
    # Rationale: LLM Prompts are NOT HTML. They are Plain Text/Markdown.
    # Python code (x > y) and Math (x < y) must NOT be escaped to (x &gt; y).
    # Auto-escaping causes "Context Poisoning" where LLMs mimic the escaped entities.
    autoescape=select_autoescape(['html', 'xml']), 
    trim_blocks=True,
    lstrip_blocks=True
)

jinja_env.filters["tojson"] = _to_json
jinja_env.filters["tex_safe"] = _tex_safe

