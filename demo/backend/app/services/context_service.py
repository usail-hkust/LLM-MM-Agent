"""
Context Service - History reconstruction with Anti-Poisoning measures.
[OPTIMIZED] Asset Stratification: Filters out non-essential binary blobs (images) 
from Sandbox Context unless required by the target node (e.g., Reporting).
"""
import logging
from typing import Tuple, Dict, List
from uuid import UUID

from app.domain.models import Project, NodeState
from app.domain.unified_io import BlockType, NodeOutput
from app.domain.registry import registry
from app.infra.persistence.repositories import VersionRepository
from app.utils.files import is_safe_for_sandbox, is_visual_asset

logger = logging.getLogger(__name__)


class ContextService:
    def __init__(self, version_repo: VersionRepository):
        self.v_repo = version_repo

    def _get_sort_key(self, node_state: NodeState) -> Tuple[int, int, int]:
        """
        Sort key: (Phase, Iteration, Sequence)
        Result: 1.x < 2.1-0 < 2.2-0 < 2.1-1 < ... < 3.x
        """
        base_id = node_state.base_id
        # 1. Phase Priority
        phase = 0 if base_id.startswith("1.") else 1 if base_id.startswith("2.") else 2
        
        # 2. Iteration Index (Static = 0)
        iter_idx = node_state.iteration_index if node_state.iteration_index is not None else 0
        
        # 3. Sequence in Registry (Tie breaker for same phase/iteration)
        seq_idx = registry.get_sequence_index(base_id)
        
        return (phase, iter_idx, seq_idx)

    async def build_history(
        self, 
        project: Project, 
        target_node_id: str,
        include_artifacts: bool = False  # [NEW] Toggle for full asset injection
    ) -> Tuple[str, Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
        """
        Builds history string AND stratifies assets.
        
        Args:
            include_artifacts: If False (Default), excludes heavy binary assets (images/PDFs) from the manifest.
                               This prevents Sandbox injection timeouts for non-reporting nodes.
                              
        Returns: (history_str, active_manifest, dormant_assets, file_schemas)
        """
        # [FIX Issue 2] Start with Global Assets snapshot
        # We accumulate the full set first, but filter it before returning
        full_manifest: Dict[str, str] = project.assets.copy()
        file_schemas: Dict[str, List[str]] = {} 

        if target_node_id == "999.999":
            target_key = (99, 99, 99)
        else:
            target_node = project.nodes.get(target_node_id)
            if not target_node: 
                active_manifest, dormant_assets = self._stratify_manifest(full_manifest, include_artifacts)
                return "(Target not found)", active_manifest, dormant_assets, {}
            target_key = self._get_sort_key(target_node)

        # 2. Collect all committed nodes that are 'before' the target
        candidates = []
        for ns in project.nodes.values():
            if ns.status == "COMMITTED" and ns.stable_version_id:
                key = self._get_sort_key(ns)
                if key < target_key: # Strict predecessors
                    candidates.append((key, ns))

        if not candidates:
             # Even with no history nodes, we must filter the initial project assets
            active_manifest, dormant_assets = self._stratify_manifest(full_manifest, include_artifacts)
            return "(No upstream history available.)", active_manifest, dormant_assets, file_schemas

        # Sort chronologically/topologically
        candidates.sort(key=lambda x: x[0])

        # 3. Fetch Versions
        version_ids = [ns.stable_version_id for _, ns in candidates]
        versions = await self.v_repo.get_batch(version_ids)
        versions_map = {v.id: v for v in versions}

        history_lines = []

        for _, ns in candidates:
            version = versions_map.get(ns.stable_version_id)
            if not version: continue

            # Asset Inheritance (Merge inputs from provenance)
            if version.provenance:
                inputs_snap = version.provenance.get("inputs_snapshot", {})
                if "file_manifest" in inputs_snap:
                    full_manifest.update(inputs_snap["file_manifest"])

            output = version.selected_output
            if not output: continue

            blueprint = registry.get(ns.base_id)
            title = blueprint.title if blueprint else ns.node_id
            iter_label = f" (Iter {ns.iteration_index + 1})" if ns.iteration_index is not None else ""
            
            # --- Anti-Poisoning Rendering & Schema Extraction ---
            node_body, node_files, node_schemas = self._render_output(output, node_id=ns.node_id)
            
            step_header = f"## Step {ns.node_id}: {title}{iter_label}\n*(Completed at {version.created_at.strftime('%Y-%m-%d %H:%M')})*"
            full_step_text = f"{step_header}\n\n{node_body}"
            
            quoted_step = "\n".join([f"> {line}" for line in full_step_text.splitlines()])
            
            history_lines.append(quoted_step)
            history_lines.append("> \n> " + "-"*40 + "\n") 
            
            # Accumulate new files and schemas
            full_manifest.update(node_files)
            file_schemas.update(node_schemas)

        # 4. [Asset Stratification] Split manifest into Active (Light) and Dormant (Heavy)
        active_manifest, dormant_assets = self._stratify_manifest(full_manifest, include_artifacts)

        return "\n".join(history_lines), active_manifest, dormant_assets, file_schemas

    def _stratify_manifest(self, manifest: Dict[str, str], force_include_all: bool) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Splits manifest into Active (Safe) and Dormant (Heavy).
        Active: Code, Text, Data (CSV/JSON) -> Always synced.
        Dormant: Images, PDFs, Videos -> Synced only via JIT.
        """
        if force_include_all:
            return manifest, {}
            
        active = {}
        dormant = {}
        
        for v_path, blob_hash in manifest.items():
            # Rule: Only allow 'Safe' files into Active Manifest
            if is_safe_for_sandbox(v_path):
                active[v_path] = blob_hash
            else:
                # Images/Binary assets are dormant
                dormant[v_path] = blob_hash
        
        return active, dormant

    def _render_output(self, output: NodeOutput, node_id: str) -> Tuple[str, Dict[str, str], Dict[str, List[str]]]:
        """
        Renders output and extracts file metadata (Manifest + Schemas).
        Returns: (text, files_map, schemas_map)
        """
        lines = []
        files = {}
        schemas = {}
        queue = list(output.blocks)
        
        while queue:
            block = queue.pop(0)
            if block.type == BlockType.CONTAINER:
                for child in reversed(block.children):
                    queue.insert(0, child)
                continue
            
            if block.type == BlockType.MARKDOWN:
                if block.content:
                    content = str(block.content).replace("\n# ", "\n### ").replace("\n## ", "\n### ")
                    if content.startswith("# "): content = "### " + content[2:]
                    lines.append(content)
            
            elif block.type == BlockType.CODE:
                lang = block.meta.get("language", "text").split(':')[0]
                lines.append(f"**[Source: {block.label}]**")
                lines.append(f"```{lang}\n{block.content or ''}\n```")
                
            elif block.type == BlockType.DATA:
                import json
                try:
                    lines.append(f"**[Data: {block.label}]**")
                    json_str = json.dumps(block.content, indent=2, ensure_ascii=False)
                    lines.append(f"```json\n{json_str}\n```")
                except:
                    lines.append(f"**[Data: {block.label} (Encoding Error)]**")
            
            elif block.type == BlockType.FILE:
                blob_hash = block.meta.get("blob_hash")
                filename = block.meta.get("filename", block.label or "file.bin")
                if blob_hash:
                    virtual_path = f"history/{node_id}/{filename}"
                    files[virtual_path] = blob_hash
                    
                    # Extract Schema from Meta
                    if "schema_columns" in block.meta:
                        schemas[virtual_path] = block.meta["schema_columns"]
                    
                    # [Visual Persistence] We render the reference even if filtered from Sandbox
                    lines.append(f"![File Reference: {filename}]({virtual_path})")
            lines.append("")

        return "\n".join(lines), files, schemas
