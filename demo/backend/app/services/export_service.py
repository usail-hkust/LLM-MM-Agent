"""
Export Service.
Orchestrates the logical-to-physical mapping for project export.
"""
import json
import logging
import re
from typing import List, Any
from uuid import UUID
from datetime import datetime

from app.domain.models import Project
from app.domain.registry import registry
from app.core.definitions import BlockType, RenderType
from app.infra.persistence.repositories import ProjectRepository, VersionRepository
from app.infra.persistence.copilot_repository import CopilotRepository
from app.infra.asset_manager import AssetManager
from app.utils.io_zip import StreamingZip, ZipEntry

logger = logging.getLogger(__name__)

class ExportService:
    def __init__(
        self, 
        p_repo: ProjectRepository,
        v_repo: VersionRepository,
        c_repo: CopilotRepository,
        assets: AssetManager
    ):
        self.p_repo = p_repo
        self.v_repo = v_repo
        self.c_repo = c_repo
        self.assets = assets

    async def export_stream(self, project_id: str):
        """Generates an async stream of the project zip archive."""
        pid = UUID(project_id)
        project = await self.p_repo.get(pid)
        if not project: 
            raise ValueError("Project not found")

        # 1. Build the logical manifest of files to export
        entries = await self._build_manifest(project)
        
        # 2. Start streaming the zip creation
        return StreamingZip.create_stream(entries, self.assets)

    async def _build_manifest(self, project: Project) -> List[ZipEntry]:
        """Traverses the project to build the file list."""
        entries = []
        # Root directory name inside the zip
        root = f"{self._sanitize(project.name)}_Export"

        # --- 1. Metadata & Global Assets ---
        meta = {
            "id": str(project.id), 
            "name": project.name,
            "owner_id": project.owner_id,
            "exported_at": datetime.utcnow().isoformat(),
            "asset_ledger": project.asset_ledger.model_dump(mode="json")
        }
        entries.append(ZipEntry(f"{root}/_metadata/project_info.json", "memory", json.dumps(meta, indent=2)))

        # Export all global assets mapped in the project
        for v_path, blob_hash in project.assets.items():
            # Use simple name for global folder, keep structure if needed
            safe_name = v_path.split("/")[-1]
            entries.append(ZipEntry(f"{root}/_global_assets/{safe_name}", "cas", blob_hash=blob_hash))

        # --- 2. Copilot Chat Logs ---
        try:
            sessions = await self.c_repo.list_sessions(str(project.id))
            for s in sessions:
                msgs = await self.c_repo.get_messages(s.id, limit=2000)
                if not msgs: continue
                
                updated_str = s.updated_at.isoformat() if hasattr(s.updated_at, 'isoformat') else str(s.updated_at)
                chat_content = f"# Chat Session: {s.title}\nID: {s.id}\nDate: {updated_str}\n\n"
                for m in msgs:
                    role_str = m.role.upper()
                    chat_content += f"## {role_str}\n"
                    if m.thought:
                        chat_content += f"> **Thought**: {m.thought}\n\n"
                    chat_content += f"{m.content}\n\n---\n\n"
                
                safe_title = self._sanitize(s.title or "Untitled_Chat")
                entries.append(ZipEntry(f"{root}/_copilot_logs/{safe_title}_{s.id[:6]}.md", "memory", chat_content))
        except Exception as e:
            logger.warning(f"Failed to export copilot logs: {e}")

        # --- 3. Node Topology Traversal ---
        # Get all blueprints in order to structure the folders
        blueprints = sorted(registry.get_all(), key=lambda b: registry.get_global_index(b.id))
        
        for bp in blueprints:
            # Find all nodes in the project derived from this blueprint
            instances = [n for n in project.nodes.values() if n.base_id == bp.id and n.status != "VOID"]
            instances.sort(key=lambda x: x.iteration_index or 0)

            for node in instances:
                # Resolve Version: Prefer Working (Draft), fallback to Stable (Committed)
                vid = node.working_version_id or node.stable_version_id
                if not vid: continue

                version = await self.v_repo.get(vid)
                if not version or not version.selected_output: continue

                # Determine Directory Structure
                # Phase -> Node
                phase_idx = registry.get_phase_index(bp.id)
                phase_dir = f"{phase_idx+1:02d}_{self._sanitize(bp.phase_label)}"
                
                # e.g. "1.1_Problem_Analysis" or "2.1-0_Model_Design"
                node_label = f"{node.node_id}_{self._sanitize(bp.title)}"
                base_path = f"{root}/{phase_dir}/{node_label}"

                # Extract content from the selected output
                await self._process_node_output(version.selected_output, base_path, entries)

        return entries

    async def _process_node_output(self, output: Any, base_path: str, entries: List[ZipEntry]):
        """Recursively processes output blocks into files."""
        file_counter = {}

        # 1. Export Thought Process
        if output.thought:
            entries.append(ZipEntry(f"{base_path}/_thought_process.md", "memory", output.thought))

        # 2. Traverse Blocks
        def traverse(blocks):
            for block in blocks:
                # A. Paper Engine Workspace (Special Handling)
                # Reconstructs the full LaTeX directory structure
                if block.render_type == RenderType.IDE_WORKSPACE and isinstance(block.content, dict):
                    # Try to get full state from meta first (complete model dump), then fallback to content
                    workspace_data = block.meta.get("full_state", {})
                    files_map = workspace_data.get("files", block.content)
                    
                    for v_path, f_data in files_map.items():
                        # f_data structure check (VirtualFile dict or simpler dict)
                        blob = f_data.get("blob_hash")
                        content = f_data.get("content")
                        
                        # Fix path delimiters and normalize
                        clean_path = v_path.replace("\\", "/")
                        full_path = f"{base_path}/Workspace/{clean_path}"
                        
                        if blob:
                            entries.append(ZipEntry(full_path, "cas", blob_hash=blob))
                        elif content is not None:
                            entries.append(ZipEntry(full_path, "memory", str(content)))
                    continue

                if block.children:
                    traverse(block.children)
                    continue

                # B. Standard Content Blocks
                ext = ".txt"
                content_str = None
                blob = block.meta.get("blob_hash")
                
                # Determine extension and content
                if block.type == BlockType.CODE:
                    lang = block.meta.get("language", "text").lower()
                    if "python" in lang: ext = ".py"
                    elif "json" in lang: ext = ".json"
                    elif "markdown" in lang or "md" in lang: ext = ".md"
                    elif "latex" in lang or "tex" in lang: ext = ".tex"
                    else: ext = ".txt"
                    content_str = str(block.content) if block.content else ""
                    
                elif block.type == BlockType.MARKDOWN:
                    ext = ".md"
                    content_str = str(block.content) if block.content else ""
                    
                elif block.type == BlockType.DATA:
                    ext = ".json"
                    content = block.content
                    if not isinstance(content, str):
                        content_str = json.dumps(content, indent=2, default=str)
                    else:
                        content_str = content
                        
                elif block.type == BlockType.FILE:
                    # Physical file -> Use CAS
                    fname = block.meta.get("filename", block.label)
                    # Fallback for label
                    if not fname: fname = "file.bin"
                    
                    if blob:
                        entries.append(ZipEntry(f"{base_path}/assets/{fname}", "cas", blob_hash=blob))
                    continue

                # Save Memory Content
                if content_str is not None:
                    # Sanitize label for filename
                    label = self._sanitize(block.label or "untitled")
                    if not label: label = "content"
                    
                    # Deduplicate filenames in same folder
                    if label in file_counter:
                        file_counter[label] += 1
                        name = f"{label}_{file_counter[label]}"
                    else:
                        file_counter[label] = 0
                        name = label
                    
                    entries.append(ZipEntry(f"{base_path}/{name}{ext}", "memory", content_str))

        traverse(output.blocks)

    def _sanitize(self, name: str) -> str:
        """Sanitizes strings for use as filenames."""
        if not name: return "untitled"
        # Replace non-alphanumeric with underscore
        clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        # Collapse multiple underscores
        clean = re.sub(r'_{2,}', '_', clean)
        return clean.strip("_")
