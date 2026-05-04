"""
Value Objects for Domain Entities.

Defines structural schemas for specific data blocks (e.g., Paper Metadata).
"""
import logging
from typing import Any

from pydantic import BaseModel, field_validator

from app.core.definitions import ContestType

logger = logging.getLogger(__name__)


class PaperMetadata(BaseModel):
    """
    Metadata required for the LaTeX template header.
    Extracted from the LLM's structured output (e.g., 'json:metadata' block).
    """
    title: str
    contest_type: ContestType = ContestType.MCM
    problem_id: str = "A"
    control_number: str = "0000000"

    @field_validator("contest_type", mode="before")
    @classmethod
    def _sanitize_contest(cls, v: Any) -> Any:
        # Allow case-insensitive string parsing for robustness
        if isinstance(v, ContestType):
            return v
        if isinstance(v, str):
            v_clean = v.upper().strip()
            # Heuristic normalization
            if v_clean in ["MCM", "ICM"]:
                return ContestType(v_clean)
            if "MCM" in v_clean:
                return ContestType.MCM
            if "ICM" in v_clean:
                return ContestType.ICM
        return ContestType.MCM