"""
Sync Service (v3.1).
[REFACTORED] Added Read-Only Protection.
Prevents remote modifications to 'main.tex' from overwriting local project state.
"""
import logging
import asyncio
from typing import Dict, Set

from app.core.config import settings
from app.infra.asset_manager import AssetManager
from app.infra.gateways.sandbox import AsyncSandbox, SandboxGateway
from app.paper_engine.domain import VirtualFile, PaperWorkspace, FileType

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, sandbox: SandboxGateway, assets: AssetManager):
        self.gw = sandbox
        self.assets = assets
        self.work_dir = settings.SANDBOX_DATA_DIR

    async def push_workspace(
        self, 
        sb: AsyncSandbox, 
        workspace: PaperWorkspace, 
        exclude: Set[str] = None
    ):
        exclude = exclude or set()
        await sb.commands.run("mkdir -p sections img data", cwd=self.work_dir)

        text_files: Dict[str, str] = {}
        blob_manifest: Dict[str, str] = {}
        
        # [FIX] Immutable Infrastructure: Agent MUST NOT edit these.
        immutable_files = {"main.tex", "easymcm.sty", "build.py", "structure.json"}
        ro_files = []

        for path, vf in workspace.files.items():
            remote_path = path
            
            # Determine read-only status for Sandbox
            if vf.is_readonly or path in immutable_files:
                ro_files.append(f"{self.work_dir}/{remote_path}")

            if path in exclude:
                continue

            if vf.blob_hash and vf.file_type == FileType.ASSET:
                blob_manifest[path] = vf.blob_hash
            elif vf.content is not None:
                text_files[remote_path] = vf.content

        # 1. Assets
        if blob_manifest:
            await self.gw.sync_manifest(sb, blob_manifest, is_new_session=False)

        # 2. Text Files
        tasks = []
        for r_path, content in text_files.items():
            tasks.append(sb.files.write(f"{self.work_dir}/{r_path}", content))
        
        if tasks:
            await asyncio.gather(*tasks)
        
        # 3. Lock ReadOnly Files (Permission Level)
        # This physically prevents the Agent from deleting lines in main.tex
        if ro_files:
            chunk_size = 50
            for i in range(0, len(ro_files), chunk_size):
                chunk = ro_files[i:i + chunk_size]
                await sb.commands.run(f"chmod 444 {' '.join(chunk)}")

    async def pull_snapshot(self, sb: AsyncSandbox, current_workspace: PaperWorkspace) -> PaperWorkspace:
        """
        [Sync Back]: Pulls modified files.
        [PROTECTION] Ignores changes to files marked 'is_readonly' in local workspace.
        """
        known = {p: f.blob_hash for p, f in current_workspace.files.items() if f.blob_hash}
        new_artifacts, full_manifest = await self.gw.harvest_artifacts_diff(sb, known)

        for fname, content in new_artifacts.items():
            # 1. Retrieve local definition
            vf = current_workspace.get_file(fname)
            
            # 2. [CRITICAL] Read-Only Guard
            # If file is Read-Only locally, we DO NOT accept remote changes (unless it's the PDF output)
            if vf and vf.is_readonly:
                if fname != "main.pdf": 
                    logger.debug(f"Sync: Refusing to pull modifications for Read-Only file {fname}")
                    continue

            # 3. Create or Update
            ftype = FileType.LATEX_PART
            if fname == "main.tex": ftype = FileType.LATEX_MAIN
            elif fname == "main.pdf": ftype = FileType.PDF_OUTPUT
            elif fname.endswith(".sty"): ftype = FileType.STYLE
            elif fname.endswith(".py"): ftype = FileType.SCRIPT
            elif fname.startswith("img/"): ftype = FileType.ASSET

            if not vf:
                vf = VirtualFile(path=fname, file_type=ftype)
                # Inherit ReadOnly if it's a known system file type
                if ftype in {FileType.LATEX_MAIN, FileType.STYLE}:
                    vf.is_readonly = True

            try:
                text = content.decode("utf-8")
                vf.content = text
                vf.blob_hash = None
            except UnicodeDecodeError:
                b_hash = await self.assets.save_bytes(content)
                vf.blob_hash = b_hash
                vf.content = None
                if fname == "main.pdf":
                    current_workspace.pdf_url = "main.pdf"

            current_workspace.files[fname] = vf

        # Handle Deletions
        if full_manifest:
            protected_files = {"build.py", "easymcm.sty", "assets_map.json", "structure.json", "main.tex"}
            for path in list(current_workspace.files.keys()):
                if path in protected_files:
                    continue
                if path not in full_manifest:
                    # Also protect ReadOnly files from being "deleted" by the Agent
                    if current_workspace.files[path].is_readonly:
                         continue
                    current_workspace.files.pop(path, None)

        return current_workspace
