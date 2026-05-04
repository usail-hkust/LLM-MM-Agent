"""
Application lifecycle hooks.

Manages startup and shutdown of the application.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.logging import setup_logging
from app.core.events import event_bus
from app.infra.gateways.sandbox import SandboxTemplateManager
from app.infra.persistence.database import init_db

logger = logging.getLogger("lcp.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # --- Startup ---
    setup_logging()
    logger.info("Application starting up...")
    
    await init_db()
    logger.info("Database initialized for local deployment.")

    # [Build System 2.0]
    # Ensure E2B Template is built and ready asynchronously.
    # We use create_task so it doesn't block the API from starting immediately,
    # though the first request might wait if it hits the sandbox early.
    asyncio.create_task(SandboxTemplateManager.ensure_template_ready())
    
    yield
    
    # --- Shutdown ---
    logger.info("Application shutting down...")
    
    # Shutdown EventBus (close all pollers first)
    await event_bus.shutdown()
    
    # No cleanup needed: Sandbox sessions are stateless (managed by E2B metadata)
    # Sessions will timeout automatically based on SANDBOX_TIMEOUT setting
