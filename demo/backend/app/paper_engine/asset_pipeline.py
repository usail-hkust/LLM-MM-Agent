"""
Asset Pipeline (Stateful).
"""
import logging
from pathlib import Path
from typing import Dict, Tuple

from app.infra.asset_manager import AssetManager
from app.paper_engine.domain import VirtualFile, FileType
from app.domain.models import Project, AssetLedgerEntry

logger = logging.getLogger(__name__)


class AssetPipeline:
    """
    Manages the transformation of assets for the Paper Engine.
    
    Refactored Principles:
    1. Stateful: Uses AssetLedger to maintain permanent IDs.
    2. Sticky: Once "heatmap.png" is "fig_01", it stays "fig_01".
    3. Anti-Loop: Pass-through existing "img/fig_..." files.
    """
    
    def __init__(self, asset_manager: AssetManager):
        self.assets = asset_manager

    async def prepare_assets(
        self,
        project: Project,
        file_manifest: Dict[str, str]
    ) -> Tuple[Dict[str, VirtualFile], Dict[str, str]]:
        """
        Returns:
            virtual_files: Dict ready for Workspace (Target Path -> VirtualFile)
            asset_map: Mapping (Original Path -> Target Path)
        """
        virtual_files: Dict[str, VirtualFile] = {}
        asset_map: Dict[str, str] = {}

        ledger = project.asset_ledger
        current_paths = set(file_manifest.keys())

        # Whitelist allowed extensions for Paper assets
        img_exts = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}

        for original_path, blob_hash in sorted(file_manifest.items()):
            path_obj = Path(original_path)
            ext = path_obj.suffix.lower()

            if ext not in img_exts:
                continue

            # --- [Rule 1] Loop Protection ---
            if original_path.startswith("img/") and (path_obj.name.startswith("fig_") or path_obj.name.startswith("asset_")):
                target_path = original_path
                if original_path not in ledger.mappings:
                    ledger.mappings[original_path] = AssetLedgerEntry(target_handle=path_obj.name)
            else:
                # --- [Rule 2] Sticky Assignment ---
                target_handle = ledger.resolve_or_assign(original_path, ext, path_obj.stem)
                target_path = f"img/{target_handle}"

            virtual_files[target_path] = self._create_vf(target_path, blob_hash, ext)
            asset_map[original_path] = target_path

        ledger.mark_missing_as_archived(current_paths)

        return virtual_files, asset_map

    async def prepare_assets_for_sandbox(
        self,
        project: Project,
        manifest: Dict[str, str]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Calculates Stable Physical Filenames using Project's AssetLedger.
        
        Returns:
            sandbox_layout: { "fig_01.png": "blob_hash" } -> For Sandbox Injection
            asset_map: { "history/2.3/plot.png": "fig_01.png" } -> For Prompt Rewriting
        """
        ledger = project.asset_ledger
        
        sandbox_layout = {}
        asset_map = {}
        
        # 1. Resolve every asset in the manifest
        current_virtual_paths = set(manifest.keys())
        
        for v_path, blob_hash in manifest.items():
            # Determine extension
            path_obj = Path(v_path)
            ext = path_obj.suffix.lower()
            
            # Whitelist allowed extensions for Paper assets
            img_exts = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}
            if ext not in img_exts:
                continue
            
            # Use Ledger to get/assign stable ID
            # e.g. "fig_01_heatmap.png"
            if v_path.startswith("img/") and (path_obj.name.startswith("fig_") or path_obj.name.startswith("asset_")):
                physical_name = path_obj.name
                if v_path not in ledger.mappings:
                    ledger.mappings[v_path] = AssetLedgerEntry(target_handle=physical_name)
            else:
                target_handle = ledger.resolve_or_assign(v_path, ext, path_obj.stem)
                physical_name = target_handle
            
            # Map for Sandbox (Physical -> Blob)
            sandbox_layout[physical_name] = blob_hash
            
            # Map for LLM (Virtual -> Physical)
            asset_map[v_path] = physical_name
            
        # 2. Archive missing assets (Tombstone)
        ledger.mark_missing_as_archived(current_virtual_paths)
        
        logger.info(f"AssetPipeline: Resolved {len(sandbox_layout)} assets for layout.")
        return sandbox_layout, asset_map

    def _create_vf(self, path: str, blob_hash: str, ext: str) -> VirtualFile:
        mime_type = "application/octet-stream"
        if ext == ".png":
            mime_type = "image/png"
        elif ext in {".jpg", ".jpeg"}:
            mime_type = "image/jpeg"
        elif ext == ".pdf":
            mime_type = "application/pdf"

        return VirtualFile(
            path=path,
            blob_hash=blob_hash,
            file_type=FileType.ASSET,
            is_readonly=True,
            mime_type=mime_type,
        )
