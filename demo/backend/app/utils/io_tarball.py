"""
High-performance tarball generators for Sandbox injection.
"""
import io
import os
import tarfile
import logging
import threading
import asyncio
import time
from pathlib import Path
from typing import Dict, Tuple, Any, AsyncGenerator

logger = logging.getLogger(__name__)


class StreamingTarball:
    """
    Optimized I/O Pipeline:
    Disk (AssetManager) -> Thread(tarfile.addfile) -> Pipe -> AsyncGenerator (Network)
    """

    @staticmethod
    def create_stream(
        manifest: Dict[str, str],
        asset_manager: Any
    ) -> AsyncGenerator[bytes, None]:
        """
        Returns an async generator yielding chunks of the .tar.gz stream.
        """
        # r_fd: Read end (Async Consumer)
        # w_fd: Write end (Sync Producer Thread)
        r_fd, w_fd = os.pipe()

        def producer():
            try:
                with os.fdopen(w_fd, "wb") as pipe_out:
                    with tarfile.open(fileobj=pipe_out, mode="w|gz", bufsize=64 * 1024) as tar:
                        for filename, blob_hash in manifest.items():
                            try:
                                parts = Path(filename).parts
                                if len(parts) > 2 and parts[0] == "history":
                                    arcname = str(Path(*parts[2:]))
                                else:
                                    arcname = filename.lstrip("/")

                                if not arcname:
                                    continue

                                try:
                                    with asset_manager.open_blob(blob_hash) as f:
                                        f.seek(0, os.SEEK_END)
                                        size = f.tell()
                                        f.seek(0)

                                        info = tarfile.TarInfo(name=arcname)
                                        info.size = size
                                        info.mtime = int(time.time())

                                        # Stream content (Zero-Copy Disk -> Pipe)
                                        tar.addfile(info, fileobj=f)
                                except FileNotFoundError:
                                    logger.warning(f"Blob {blob_hash} missing for {filename}")
                            except Exception as e:
                                logger.error(f"Error adding {filename} to tar: {e}")
            except Exception as e:
                logger.error(f"Tarball producer failed: {e}")

        t = threading.Thread(target=producer, daemon=True)
        t.start()

        async def reader():
            loop = asyncio.get_running_loop()
            chunk_size = 64 * 1024
            try:
                while True:
                    chunk = await loop.run_in_executor(None, os.read, r_fd, chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                os.close(r_fd)
                t.join(timeout=1.0)

        return reader()


class IoTarball:
    """
    Legacy in-memory tarball generator (avoid for large payloads).
    """

    @staticmethod
    async def create_from_manifest(
        manifest: Dict[str, str],
        asset_manager: Any
    ) -> Tuple[bytes, int]:
        """
        Creates a tarball from a virtual manifest (Filename -> BlobHash).
        Reads bytes asynchronously from AssetManager (CAS).
        """
        buffer = io.BytesIO()
        count = 0

        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for filename, blob_hash in manifest.items():
                try:
                    data = await asset_manager.get_asset_bytes(blob_hash)
                except Exception as e:
                    logger.warning(f"IoTarball: Failed to read {filename}: {e}")
                    data = None

                if not data:
                    continue

                parts = Path(filename).parts
                if len(parts) > 2 and parts[0] == "history":
                    arcname = str(Path(*parts[2:]))
                else:
                    arcname = filename.lstrip("/")

                if not arcname:
                    continue

                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                count += 1

        buffer.seek(0)
        return buffer.getvalue(), count

    @staticmethod
    def create_in_memory(files: Dict[str, bytes]) -> Tuple[bytes, int]:
        """
        Synchronous helper for raw bytes dict.
        """
        buffer = io.BytesIO()
        count = 0
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name, data in files.items():
                if not data:
                    continue
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                count += 1
        buffer.seek(0)
        return buffer.getvalue(), count
