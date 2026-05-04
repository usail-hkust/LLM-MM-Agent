"""
Asset Manager - Content-Addressable Storage (CAS).

Manages the lifecycle of binary artifacts via Content-Addressable Storage.
Supports Zero-Copy streaming for high-performance I/O with E2B.
"""
import logging
import asyncio
import hashlib
import shutil
import httpx
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, Any, List, BinaryIO
from contextlib import contextmanager

from app.core.config import settings
from app.core.definitions import BlockType
from app.domain.unified_io import NodeOutput, ContentBlock
from app.utils.hashing import compute_sha256
from app.utils.files import ensure_dir
from app.utils.io_tarball import IoTarball

logger = logging.getLogger(__name__)


class AssetManager:
    """
    Manages the lifecycle of binary artifacts via Content-Addressable Storage (CAS).
    Merges the roles of BlobStorage and ArtifactLinker.
    """
    
    def __init__(self, storage_root: str = None):
        # Allow dependency injection for testability, default to settings
        root_str = storage_root or settings.STORAGE_ROOT
        
        # Resolve path: if relative, resolve relative to backend/ directory (consistent with templates.py)
        # If absolute, use as-is
        if Path(root_str).is_absolute():
            self.root = Path(root_str)
        else:
            # Get backend directory (parent of app/)
            backend_dir = Path(__file__).resolve().parent.parent.parent
            self.root = backend_dir / root_str
        
        ensure_dir(self.root)
        
        # Temp directory for streaming downloads
        self.tmp_dir = self.root / "_tmp"
        ensure_dir(self.tmp_dir)

    async def save_bytes(self, data: bytes) -> str:
        """
        [New] Direct Save Method.
        Persists raw bytes and returns the SHA256 hash.
        Used for file uploads API.
        """
        if not data:
            raise ValueError("Cannot save empty data")
            
        blob_hash = compute_sha256(data)
        await self._write_blob(blob_hash, data)
        return blob_hash

    async def process_and_save(self, output: NodeOutput) -> NodeOutput:
        """
        [Write Path]
        Scans a NodeOutput for blocks of type FILE with binary content.
        Persists them to disk (CAS) and replaces the content with a reference.
        Returns a modified NodeOutput safe for DB persistence.
        """
        # We assume NodeOutput structure might be recursive (CONTAINER), 
        # so we use a helper to traverse.
        new_blocks = await self._process_blocks_recursive(output.blocks)
        
        # Return a copy with modified blocks
        return output.model_copy(update={"blocks": new_blocks})

    async def hydrate_manifest(self, file_map: Dict[str, str]) -> Dict[str, bytes]:
        """
        [Read Path]
        Resolves a virtual file map (Virtual Path -> Blob Hash) into 
        physical bytes for Sandbox injection.
        """
        assets = {}
        for v_path, blob_hash in file_map.items():
            data = await self._read_blob(blob_hash)
            if data:
                assets[v_path] = data
            else:
                logger.warning(f"Blob missing for {v_path}: {blob_hash}")
        return assets
    
    async def save_stream_from_url(self, url: str) -> Dict[str, Any]:
        """
        [Smart I/O] Zero-Copy Save from URL.
        Streams data from a URL (e.g., E2B Signed URL) directly to CAS.
        Calculates SHA256 on-the-fly. Does NOT load the file into RAM.
        """
        loop = asyncio.get_running_loop()
        # Run blocking stream I/O in executor to avoid blocking event loop
        return await loop.run_in_executor(None, self._save_stream_sync, url)

    def _save_stream_sync(self, url: str) -> Dict[str, Any]:
        """Blocking stream download operation."""
        # Create temp file
        fd, temp_path = tempfile.mkstemp(dir=self.tmp_dir)
        sha256_hash = hashlib.sha256()
        total_size = 0

        try:
            # Stream download
            with httpx.stream("GET", url, follow_redirects=True, verify=False) as response:
                response.raise_for_status()
                with os.fdopen(fd, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        sha256_hash.update(chunk)
                        total_size += len(chunk)

            blob_hash = sha256_hash.hexdigest()
            final_path = self._get_blob_path(blob_hash)
            
            if not final_path.exists():
                ensure_dir(final_path.parent)
                # Atomic move
                shutil.move(temp_path, final_path)
            else:
                # Dedup: File exists
                os.remove(temp_path)
                
            return {
                "blob_hash": blob_hash,
                "size_bytes": total_size,
                "storage": "local_cas"
            }
            
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Failed to stream save from URL {url}: {e}")
            raise e

    @contextmanager
    def open_blob(self, blob_hash: str) -> BinaryIO:
        """
        Returns a file handle to the blob data.
        Used for streaming uploads to Sandbox without loading into RAM.
        """
        path = self._get_blob_path(blob_hash)
        if not path.exists():
            raise FileNotFoundError(f"Blob {blob_hash} not found")
        
        f = open(path, "rb")
        try:
            yield f
        finally:
            f.close()

    async def get_asset_bytes(self, blob_hash: str) -> Optional[bytes]:
        """Direct retrieval by hash."""
        return await self._read_blob(blob_hash)

    def get_blob_size(self, blob_hash: str) -> int:
        """
        [NEW] Get size of a blob in bytes without reading it.
        Used for chunking strategy in Sandbox sync to prevent OOM/Timeouts.
        """
        path = self._get_blob_path(blob_hash)
        if path.exists():
            return path.stat().st_size
        return 0

    async def create_tarball(self, manifest: Dict[str, str]):
        """Facade for IoTarball (virtual manifest -> tar.gz bytes)."""
        return await IoTarball.create_from_manifest(manifest, self)

    # --- Internal Helpers ---

    async def _process_blocks_recursive(self, blocks: List[ContentBlock]) -> List[ContentBlock]:
        processed_blocks = []
        for block in blocks:
            if block.type == BlockType.CONTAINER and block.children:
                # Recursion
                new_children = await self._process_blocks_recursive(block.children)
                new_block = block.model_copy(update={"children": new_children})
                processed_blocks.append(new_block)
                
            elif block.type == BlockType.FILE and isinstance(block.content, (bytes, bytearray)):
                # Found binary content -> Persist
                blob_hash = compute_sha256(block.content)
                await self._write_blob(blob_hash, block.content)
                
                # Update Metadata
                new_meta = block.meta.copy()
                new_meta.update({
                    "blob_hash": blob_hash,
                    "size_bytes": len(block.content),
                    "storage": "local_cas"
                })

                # Replace Block Content with None (Reference Only)
                new_block = block.model_copy(update={
                    "content": None,
                    "meta": new_meta
                })
                processed_blocks.append(new_block)
                logger.info(f"Persisted asset {block.label} -> {blob_hash[:8]}")
                
            else:
                processed_blocks.append(block)
                
        return processed_blocks

    async def _write_blob(self, blob_hash: str, data: bytes):
        """Write blob to disk (Async I/O wrapper)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_blob_sync, blob_hash, data)

    def _get_blob_path(self, blob_hash: str) -> Path:
        if len(blob_hash) < 4:
            raise ValueError("Invalid hash")
        prefix1 = blob_hash[:2]
        prefix2 = blob_hash[2:4]
        return self.root / prefix1 / prefix2 / blob_hash

    def _write_blob_sync(self, blob_hash: str, data: bytes):
        """Blocking write operation."""
        target = self._get_blob_path(blob_hash)
        if not target.exists():
            ensure_dir(target.parent)
            # Write atomic (write temp then rename) logic could be added here
            # For now, standard write (can be made async with aiofiles if needed)
            with open(target, "wb") as f:
                f.write(data)

    async def _read_blob(self, blob_hash: str) -> Optional[bytes]:
        """Read blob from disk (Async I/O wrapper)."""
        if not blob_hash or len(blob_hash) < 4:
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_blob_sync, blob_hash)

    def _read_blob_sync(self, blob_hash: str) -> Optional[bytes]:
        """Blocking read operation."""
        target = self._get_blob_path(blob_hash)
        if target.exists():
            # Can be made async with aiofiles if needed for high concurrency
            with open(target, "rb") as f:
                return f.read()
        return None
