"""
Structured logging setup.
[OPTIMIZED] Uses QueueHandler/QueueListener for non-blocking Async I/O.
"""
import logging
import logging.handlers
import sys
import atexit
from queue import Queue
from app.core.config import settings


class _E2BNoiseFilter(logging.Filter):
    """Drop high-volume E2B polling noise while keeping warnings/errors."""

    _NOISE_SUBSTRINGS = (
        "api.e2b.dev/templates/",
        "logsOffset=",
        "HTTP Request: GET https://api.e2b.dev/",
        "Request GET https://api.e2b.dev/",
        "Response: 200 https://api.e2b.dev/",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        message = record.getMessage()
        return not any(s in message for s in self._NOISE_SUBSTRINGS)


# Global listener reference to ensure it stays alive and can be stopped
_log_listener = None


def setup_logging():
    """
    Configure application-wide logging with Non-Blocking QueueHandler.
    This prevents slow stdout/file writes from blocking the asyncio event loop.
    """
    global _log_listener
    
    # Idempotency check
    if _log_listener:
        return

    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 1. Create the Blocking Handlers (Actual I/O)
    # These will run in a separate background thread managed by QueueListener
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_format)
    
    # 2. Create the Non-Blocking Frontend (Queue)
    # Use a large queue to handle bursts from LLM streaming
    log_queue = Queue(maxsize=10000)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    
    # 3. Create and Start the Listener
    # respect_handler_level=True ensures handlers' own levels are respected
    _log_listener = logging.handlers.QueueListener(
        log_queue, 
        stream_handler, 
        respect_handler_level=True
    )
    _log_listener.start()
    
    # Register cleanup to flush logs on shutdown
    atexit.register(stop_logging)
    
    # 4. Configure Root Logger to use the QueueHandler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to prevent duplication
    root_logger.handlers = []
    
    # Add ONLY the QueueHandler to the root logger
    # All logs from the app will go to Queue -> Background Thread -> Stdout
    root_logger.addHandler(queue_handler)

    # 5. Apply Filters and Silence Noisy Libraries
    logging.getLogger().addFilter(_E2BNoiseFilter())
    
    silence_list = [
        "httpx", "httpcore", "multipart", 
        "LiteLLM", "litellm", "aiosqlite",
        "e2b", "e2b_code_interpreter", "e2b.api"
    ]
    
    for lib in silence_list:
        logging.getLogger(lib).setLevel(logging.WARNING)


def stop_logging():
    """Flush and stop the logging thread."""
    global _log_listener
    if _log_listener:
        _log_listener.stop()
        _log_listener = None

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
