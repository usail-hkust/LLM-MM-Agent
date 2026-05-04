"""
Application middleware for observability and exception handling.
"""
import time
import uuid
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exceptions import LCPError

logger = logging.getLogger("lcp.access")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking and exception mapping."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        
        # Inject Request ID into logging context (conceptually)
        # In a real app we might use contextvars here
        
        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            return response
        except Exception as exc:
            if not isinstance(exc, (LCPError, StarletteHTTPException)):
                logger.error(f"Request Panic [{request_id}]: {exc}", exc_info=True)
            else:
                logger.warning(f"Request Error [{request_id}]: {exc}")
            return self._map_exception(exc, request_id)

    def _map_exception(self, exc: Exception, req_id: str):
        """Map domain exceptions to HTTP status codes."""
        if isinstance(exc, StarletteHTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "req_id": req_id}}
            )

        if isinstance(exc, LCPError):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if exc.code == "NOT_FOUND":
                status_code = 404
            elif exc.code == "INVALID_STATE":
                status_code = 409
            elif exc.code == "UNAUTHORIZED":
                status_code = 401
            elif exc.code == "EXECUTION_FAILED":
                status_code = 502
            
            return JSONResponse(
                status_code=status_code,
                content={"error": {"code": exc.code, "message": exc.message, "meta": exc.meta, "req_id": req_id}}
            )
        
        # Fallback for unhandled exceptions
        return JSONResponse(
            status_code=500, 
            content={"error": {"code": "PANIC", "message": "Internal Server Error", "req_id": req_id}}
        )
