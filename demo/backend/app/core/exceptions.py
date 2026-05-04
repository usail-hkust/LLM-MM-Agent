"""
Unified exception hierarchy.

Domain exceptions are decoupled from HTTP status codes.
HTTP layer maps these to appropriate status codes.
"""
from typing import Any, Dict, Optional


class LCPError(Exception):
    """Base Domain Exception for the LCP Platform."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", meta: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code
        self.meta = meta or {}
        super().__init__(self.message)


class StateError(LCPError):
    """Illegal state transition (e.g. Commit a void node)."""
    def __init__(self, reason: str):
        super().__init__(reason, "INVALID_STATE")


class ResourceNotFoundError(LCPError):
    """Entity not found."""
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} '{id}' not found", "NOT_FOUND")


class ExecutionError(LCPError):
    """Compute layer failure (LLM/Sandbox)."""
    def __init__(self, source: str, details: str):
        super().__init__(f"Execution failed in {source}: {details}", "EXECUTION_FAILED")


class ExecutionFailedError(LCPError):
    """Node execution failed during processing."""
    def __init__(self, node_id: str, message: str, error_code: str = "ERROR"):
        super().__init__(f"Node {node_id} execution failed: {message}", "EXECUTION_FAILED", meta={"node_id": node_id, "error_code": error_code})


class AuthenticationError(LCPError):
    """Auth failures."""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(detail, "UNAUTHORIZED")

