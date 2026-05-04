"""
Streaming Zip Utility.
[FIXED] Switched to Threading to fix cross-platform file descriptor issues.
Uses zlib (GIL-releasing) compression for efficient streaming without blocking the Event Loop.
"""
import os
import zipfile
import threading
import asyncio
import time
import logging
import shutil
from typing import Any, AsyncGenerator, List, Union, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ZipEntry:
    """Archive entry definition"""
    arcname: str                  # Path inside ZIP
    source_type: str              # "memory" | "cas"
    content: Union[str, bytes, None] = None
    blob_hash: Optional[str] = None


class StreamingZip:
    @staticmethod
    def create_stream(
        entries: List[ZipEntry],
        asset_manager: Any
    ) -> AsyncGenerator[bytes, None]:
        """
        Creates an async generator that yields chunks of a ZIP file.
        Uses a separate THREAD for compression to ensure valid file descriptors
        while maintaining non-blocking I/O via the pipe.
        """
        # Create a pipe
        r_fd, w_fd = os.pipe()

        def producer():
            try:
                # Open the write-end of the pipe as a file
                # Buffer size 64KB for efficient writes
                with os.fdopen(w_fd, "wb") as pipe_out:
                    with zipfile.ZipFile(pipe_out, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                        for entry in entries:
                            try:
                                zinfo = zipfile.ZipInfo(filename=entry.arcname)
                                zinfo.date_time = time.localtime(time.time())[:6]
                                zinfo.compress_type = zipfile.ZIP_DEFLATED
                                # Set permissions (Unix: 644)
                                zinfo.external_attr = 0o100644 << 16

                                if entry.source_type == "memory":
                                    data = entry.content
                                    if isinstance(data, str):
                                        data = data.encode("utf-8")
                                    # Ensure data is bytes
                                    if data is None: 
                                        data = b""
                                    zf.writestr(zinfo, data)

                                elif entry.source_type == "cas" and entry.blob_hash:
                                    try:
                                        # Use asset_manager directly (Thread-safe read)
                                        # This is robust against storage path changes
                                        with asset_manager.open_blob(entry.blob_hash) as src:
                                            with zf.open(zinfo, mode="w") as dest:
                                                # Efficient stream copy (64KB chunks)
                                                shutil.copyfileobj(src, dest, length=64*1024)
                                    except FileNotFoundError:
                                        logger.warning(f"ZIP: Asset missing {entry.blob_hash} for {entry.arcname}")
                                        zf.writestr(entry.arcname + ".MISSING", b"Asset missing in storage.")
                                    except Exception as e:
                                        logger.error(f"ZIP: Failed to read asset {entry.blob_hash}: {e}")
                                        zf.writestr(entry.arcname + ".ERROR", f"Read error: {str(e)}".encode())

                            except Exception as e:
                                logger.error(f"ZIP: Failed to add entry {entry.arcname}: {e}")
                                
            except (BrokenPipeError, OSError):
                # Consumer stopped reading (e.g. client disconnect), stop silently
                pass
            except Exception as e:
                logger.error(f"ZIP Producer Crashed: {e}", exc_info=True)
            # w_fd is closed automatically by 'with os.fdopen' when exiting the block

        # Start Producer Thread (Daemon ensures it dies if main process dies)
        t = threading.Thread(target=producer, daemon=True)
        t.start()

        # Async Consumer: Reads from the pipe
        async def reader():
            loop = asyncio.get_running_loop()
            chunk_size = 64 * 1024
            try:
                while True:
                    # Run blocking read in executor to avoid blocking the Event Loop
                    chunk = await loop.run_in_executor(None, os.read, r_fd, chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                os.close(r_fd)
                # Allow thread to cleanup gracefully, but don't block long
                t.join(timeout=0.1)

        return reader()
