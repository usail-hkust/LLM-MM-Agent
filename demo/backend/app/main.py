"""
Main Application - FastAPI application entry point.
"""
# [OPTIMIZED] Install uvloop policy immediately for high-performance Event Loop
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass  # Fallback to standard asyncio if not installed

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.core.middleware import ObservabilityMiddleware
from app.core.lifecycle import lifespan
from app.core.logging import setup_logging
from app.api.auth import router as auth_router
from app.api.routes import router as api_router
from app.api.validate import router as validate_router  # [NEW] Validation API

# Configure global logging immediately
setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        lifespan=lifespan
    )

    # Custom Exception Handler for Validation Errors
    # Prevents 500 Internal Server Error when inputs contain non-UTF8 bytes (fixes jsonable_encoder crash)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        safe_errors = []
        for error in exc.errors():
            safe_error = error.copy()
            if "input" in safe_error:
                val = safe_error["input"]
                if isinstance(val, bytes):
                    try:
                        safe_error["input"] = val.decode("utf-8")
                    except UnicodeDecodeError:
                        safe_error["input"] = val.decode("latin-1", errors="replace")
            safe_errors.append(safe_error)
        
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(safe_errors)},
        )

    # 1. Routes
    app.include_router(auth_router, prefix=f"{settings.API_PREFIX}/auth", tags=["Auth"])
    app.include_router(api_router, prefix=settings.API_PREFIX, tags=["Workflow"])
    app.include_router(validate_router, prefix=settings.API_PREFIX, tags=["Validate"])

    # 2. Middleware Stack
    # Order matters: The last one added wraps the previous ones.
    # We want: Request -> CORS -> Observability -> Router
    # So we add Observability FIRST, then CORS LAST.
    app.add_middleware(ObservabilityMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    # Note: Uvicorn uses uvloop by default, but the explicit install above ensures 
    # it's active even if run via other entry points or for internal background loops.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
