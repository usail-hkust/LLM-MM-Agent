"""
Paper Engine Manager (v3.3).
[REFACTORED]
- Supports dual-mode compilation strategy.
- 'auto_fix' delegates to the fully autonomous BuildAgent prompt.
- [OPTIMIZED] Sequential Drafting Pipeline with Context Awareness (v3.1).
- [FIX] Artifact-First Error Handling: Implemented Soft Failure for Drafting and Compilation.
"""
import asyncio
import logging
import re
from uuid import UUID
from typing import Dict, List, Any, Optional, Set

from app.core.events import EventBus
from app.core.config import settings
from app.core.definitions import SystemTags, BlockType
from app.core.exceptions import ExecutionError
from app.infra.gateways.sandbox import SandboxGateway
from app.infra.gateways.llm import LLMGateway
from app.infra.asset_manager import AssetManager
from app.infra.persistence.repositories import ProjectRepository
from app.infra.persistence.database import AsyncSessionLocal
from app.paper_engine.scaffolding import Scaffolder
from app.paper_engine.asset_pipeline import AssetPipeline
from app.paper_engine.sync_service import SyncService
from app.paper_engine.build_agent import BuildAgent
from app.paper_engine.domain import PaperWorkspace, WritingTask, FileType, CompileStatus, BuildReport
from app.services.prompt_factory import PromptFactory
from app.api.schemas import RuntimeConfig

logger = logging.getLogger(__name__)


class DraftingContext:
    """
    Helper container to manage the rolling context window for sequential drafting.
    Prevents Context Window explosion by truncating older history while preserving
    immediate context for coherence.
    """
    def __init__(self):
        # List of dicts: {'title': str, 'content': str, 'success': bool}
        self._sections: List[Dict[str, Any]] = []

    def add_section(self, title: str, content: str, success: bool = True):
        self._sections.append({
            "title": title,
            "content": content,
            "success": success
        })

    def get_context_string(self) -> str:
        """
        Formats the context for the LLM.
        Strategy:
        1. Immediate Predecessor (N-1): Included with high fidelity (Critical for transitions).
        2. Historical Sections (N-k): Summarized/Truncated to save tokens.
        """
        if not self._sections:
            return ""
        
        parts = []
        count = len(self._sections)
        
        for i, sec in enumerate(self._sections):
            is_last = (i == count - 1)
            title = sec['title']
            content = sec['content']
            
            # Handle failed sections explicitly
            if not sec['success']:
                parts.append(f"## Section: {title}\n[CONTENT MISSING - GENERATION FAILED]")
                continue

            if is_last:
                # Previous Neighbor: Keep full context (up to reasonable limit)
                safe_content = content
                if len(content) > 5000:
                     safe_content = "..." + content[-5000:]
                parts.append(f"## Section: {title} (Immediate Predecessor)\n{safe_content}")
            else:
                # Historical Summary: Keep Head & Tail
                if len(content) > 500:
                    summary = content[:350] + "\n\n... [Content Truncated for Brevity] ...\n\n" + content[-150:]
                    parts.append(f"## Section: {title}\n{summary}")
                else:
                    parts.append(f"## Section: {title}\n{content}")

        
        return "\n\n".join(parts)


class PaperEngineManager:
    def __init__(
        self,
        sandbox: SandboxGateway,
        assets: AssetManager,
        llm: LLMGateway,
        prompts: PromptFactory,
        event_bus: Optional[EventBus] = None
    ):
        self.sandbox = sandbox
        self.assets = assets
        self.llm = llm
        self.prompts = prompts
        self.scaffolder = Scaffolder()
        self.pipeline = AssetPipeline(assets)
        self.sync = SyncService(sandbox, assets)
        self.agent = BuildAgent(sandbox)
        self.bus = event_bus
        # Semaphore is deprecated in Pipeline Mode
        self.drafting_semaphore = asyncio.Semaphore(1)
        self.p_repo = ProjectRepository()

    async def initialize_workspace(
        self,
        project_id: str,
        outline: List[Any],
        file_manifest: Dict[str, str],
        metadata: Dict[str, Any],
        context_str: str,
        event_bus: Optional[EventBus] = None,
        node_id: Optional[str] = None,
        timeout: int = settings.SANDBOX_EXECUTION_TIMEOUT,
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        asset_map: Optional[Dict[str, str]] = None,  # [FIX] Virtual -> Physical
        sandbox_layout: Optional[Dict[str, str]] = None,  # [FIX] Physical -> Hash
        instruction: str = ""  # [FIX] User instruction
    ) -> PaperWorkspace:
        """
        Tri-Stage Pipeline:
        1. Scaffolding: Create file structure & Writing Tasks.
        2. Drafting: Sequentially write content for all sections (Pipeline Mode).
        3. Materialization: Sync to Sandbox & Compile.
        
        [FIX] Implemented Artifact-First Error Handling (Soft Failure).
        Exceptions in Stage 2/3 are captured in the workspace state, returning partial data
        instead of crashing the workflow.
        """
        logger.info(f"Initializing Workspace {project_id}")
        self.bus = event_bus or self.bus

        pid = UUID(project_id)

        # Stage 1: Stabilize Assets with Ledger (Critical System Step - Fail Fast allowed)
        await self._emit(project_id, node_id, {"type": "thought", "content": "Stage 1: Stabilizing Assets..."})
        
        # [FIX] Use provided asset_map and sandbox_layout if available, otherwise resolve them
        if asset_map is None or sandbox_layout is None:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    project = await self.p_repo.get(pid, session=session)
                    if not project:
                        raise ExecutionError("PaperEngine", "Project not found")

                    v_assets, assets_map = await self.pipeline.prepare_assets(project, file_manifest)
                    # Generate sandbox_layout from v_assets
                    if sandbox_layout is None:
                        sandbox_layout = {}
                        for path, vf in v_assets.items():
                            if vf.blob_hash:
                                # Extract physical filename (e.g., "img/fig_01.png" -> "fig_01.png")
                                physical_name = path.split("/")[-1] if "/" in path else path
                                sandbox_layout[physical_name] = vf.blob_hash
                    
                    if asset_map is None:
                        asset_map = assets_map
                    
                    await self.p_repo.save(project, session=session)
        else:
            # Use provided mappings, but still need to create v_assets for workspace
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    project = await self.p_repo.get(pid, session=session)
                    if not project:
                        raise ExecutionError("PaperEngine", "Project not found")
                    
                    v_assets, _ = await self.pipeline.prepare_assets(project, file_manifest)
                    await self.p_repo.save(project, session=session)

        structure, writing_tasks = self.scaffolder.generate_skeleton(project_id, outline, metadata, asset_map)

        ws = PaperWorkspace(project_id=project_id)
        ws.files.update(v_assets)
        ws.files.update(structure)

        # Stage 2: Drafting (Sequential Pipeline)
        # [FIX] Soft Failure Wrapper
        if writing_tasks:
            msg = f"Stage 2: Drafting {len(writing_tasks)} sections sequentially (Pipeline Mode)..."
            logger.info(msg)
            await self._emit(project_id, node_id, {"type": "thought", "content": msg})

            # [FIX] Use physical filenames from sandbox_layout for scoped asset distribution
            physical_files = []
            if sandbox_layout:
                physical_files = list(sandbox_layout.keys())
            else:
                physical_files = [f.split("/")[-1] for f in ws.files.keys() if f.startswith("img/")]
            
            symbol_table = metadata.get("symbol_table", {}) if metadata else {}
            
            # [FIX] Physicalize context string to use physical filenames
            physical_context_str = self._physicalize_text(context_str or "", asset_map or {})

            try:
                await self._pipeline_draft_content(
                    ws,
                    writing_tasks,
                    physical_context_str,  # [FIX] Use physicalized context
                    physical_files,
                    symbol_table=symbol_table,
                    project_id=project_id,
                    node_id=node_id,
                    runtime=runtime,  # [BYOK]
                    asset_map=asset_map,  # [FIX] Pass asset_map for consumption tracking
                    sandbox_layout=sandbox_layout,  # [FIX] Pass sandbox_layout
                    instruction=instruction  # [FIX] Pass user instruction
                )
            except Exception as e:
                # Catch drafting panics (though pipeline_draft_content catches most internally)
                logger.error(f"Drafting Stage Failed: {e}", exc_info=True)
                ws.compile_status = CompileStatus.ERROR
                ws.last_build_log = f"[Drafting Panic] {str(e)}\n" + ws.last_build_log
                ws.last_build_report = BuildReport(
                    success=False,
                    exit_code=1,
                    logs=ws.last_build_log,
                    error_summary="Critical error during content drafting."
                )

        # Stage 3: Materialization & Agentic Verification
        # [FIX] Soft Failure Wrapper
        await self._emit(project_id, node_id, {"type": "thought", "content": "Stage 3: Syncing and Verifying Build..."})

        try:
            # [FIX] Use sandbox_layout if provided, otherwise build from workspace
            if sandbox_layout:
                asset_manifest = sandbox_layout
            else:
                asset_manifest = {
                    path.split("/")[-1]: vf.blob_hash  # Extract filename only
                    for path, vf in ws.files.items()
                    if vf.file_type == FileType.ASSET and vf.blob_hash
                }

            # [FIX] Use layout parameter for exact placement
            sb = await self.sandbox.start_agentic_session(
                project_id, 
                "paper-engine", 
                runtime=runtime, 
                layout=asset_manifest if asset_manifest else None
            )  # [BYOK]
            await self.sync.push_workspace(sb, ws, exclude=set(asset_manifest.keys()))

            # Always delegate initial build to Agent to fix any minor drafting errors
            await self._emit(project_id, node_id, {"type": "thought", "content": "Delegating initial build to Agent..."})

            async for log in self.agent.delegate_autonomous_fix(sb, ws, timeout=timeout, runtime=runtime):  # [BYOK]
                await self._emit(project_id, node_id, log)

            # Pull back the fixed workspace
            ws = await self.sync.pull_snapshot(sb, ws)
            
            # [FIX] Ensure PDF is harvested if compilation succeeded
            if ws.compile_status == CompileStatus.SUCCESS:
                pdf_file = ws.files.get("main.pdf")
                if pdf_file and not pdf_file.blob_hash:
                    # PDF was created but not yet persisted to CAS
                    try:
                        from app.core.config import settings
                        pdf_bytes = await sb.files.read(
                            f"{settings.SANDBOX_DATA_DIR}/main.pdf",
                            format="bytes"
                        )
                        if pdf_bytes:
                            blob_hash = await self.assets.save_bytes(pdf_bytes)
                            pdf_file.blob_hash = blob_hash
                            pdf_file.content = None
                            logger.info(f"PDF compiled and harvested: {blob_hash[:8]} ({len(pdf_bytes)} bytes)")
                    except Exception as e:
                        logger.warning(f"Compilation success but failed to harvest PDF: {e}")
            
        except Exception as e:
            # Catch infrastructure/compilation panics
            logger.error(f"Build/Verification Stage Failed: {e}", exc_info=True)
            ws.compile_status = CompileStatus.ERROR
            err_msg = f"\n[Infrastructure Error] Failed to complete build verification: {str(e)}"
            ws.last_build_log += err_msg
            await self._emit(project_id, node_id, {"type": "error", "content": err_msg})
            
            # Note: We return 'ws' as is. It contains the local state (drafts) 
            # so the user can at least see/edit the LaTeX source.
        return ws

    async def _pipeline_draft_content(
        self,
        workspace: PaperWorkspace,
        tasks: List[WritingTask],
        context_str: str,
        file_list: List[str],
        symbol_table: Optional[Dict[str, str]] = None,
        project_id: Optional[str] = None,
        node_id: Optional[str] = None,
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        asset_map: Optional[Dict[str, str]] = None,  # [FIX] Virtual -> Physical mapping
        sandbox_layout: Optional[Dict[str, str]] = None,  # [FIX] Physical -> Hash mapping
        instruction: str = ""  # [FIX] User instruction
    ):
        """
        [Pipeline Pattern]
        Executes drafting tasks sequentially to ensure context coherence and respect rate limits.
        """
        symbol_table = symbol_table or {}
        errors = []
        drafting_ctx = DraftingContext()
        
        # [FIX] State-Aware Asset Distribution: Track consumed assets
        consumed_assets: Set[str] = set()  # Stores PHYSICAL filenames
        
        total_tasks = len(tasks)
        
        for idx, task in enumerate(tasks):
            step_msg = f"Drafting [{idx+1}/{total_tasks}]: {task.title}..."
            logger.info(step_msg)
            if project_id and node_id:
                await self._emit(project_id, node_id, {"type": "thought", "content": step_msg})

            accumulated_context = drafting_ctx.get_context_string()
            
            # [FIX] Determine Scoped Candidates (Physical Paths) for this section
            scoped_physical_assets = []
            
            # Priority: Auto-Fill with Unconsumed Assets
            # Only if this is a content-heavy section (skip intro/conclusion for auto-fill to avoid noise)
            is_summary_section = any(k in task.title.lower() for k in ["intro", "conclu", "summary", "abstract", "reference"])
            if not is_summary_section:
                # Token Bucket: Grab available assets
                for physical_name in file_list:
                    if physical_name not in consumed_assets and (not sandbox_layout or physical_name in sandbox_layout):
                        scoped_physical_assets.append(physical_name)
            
            # Sort for determinism
            scoped_physical_assets.sort()
            
            try:
                msgs = self.prompts.create_task_messages(
                    template_path="paper_engine/prompts/writer.j2",
                    context={
                        "section": task,
                        "global_history": context_str,  # Already physicalized
                        "accumulated_context": accumulated_context,
                        "file_list": scoped_physical_assets,  # [FIX] Scoped List
                        "symbol_table": symbol_table,
                        "user_instruction": instruction  # [FIX] Pass user instruction
                    }
                )

                if idx > 0:
                    await asyncio.sleep(1.0)
                
                output = await self.llm.generate(msgs, temperature=0.7, runtime=runtime)  # [BYOK]

                body_content = ""
                block = output.get_block("section_content") or output.get_block("latex") or output.get_block("body")
                
                if block and block.content:
                    body_content = str(block.content)
                elif output.blocks:
                    first = output.blocks[0]
                    if first.type == BlockType.MARKDOWN and first.content:
                        body_content = str(first.content)

                if body_content:
                    vf = workspace.files.get(task.target_path)
                    if vf:
                        original = vf.content or ""
                        if task.placeholder in original:
                            vf.content = original.replace(task.placeholder, body_content)
                        else:
                            vf.content = f"{original}\n{body_content}" if original else body_content
                    
                    # [FIX] Feedback Loop: Track Consumption
                    # Regex to find \includegraphics{filename}
                    matches = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', body_content)
                    
                    found_new = 0
                    for m in matches:
                        # Clean path (remove folder prefixes if any)
                        fname = m.replace("\\", "/").split("/")[-1]
                        if fname in (sandbox_layout or {}) or fname in file_list:
                            consumed_assets.add(fname)
                            found_new += 1
                    
                    if found_new > 0:
                        logger.info(f"Section '{task.title}' consumed {found_new} assets.")
                    
                    drafting_ctx.add_section(task.title, body_content, success=True)
                    logger.info(f"Drafted {task.target_path} ({len(body_content)} chars)")
                else:
                    logger.warning(f"No content generated for {task.target_path}")
                    drafting_ctx.add_section(task.title, "", success=False)
                    errors.append(f"{task.title}: Empty response")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to draft section {task.title}: {error_msg}")
                errors.append(f"{task.title}: {error_msg}")
                
                vf = workspace.files.get(task.target_path)
                if vf:
                    placeholder_text = f"% [MISSING CONTENT: Section '{task.title}' failed to generate: {error_msg}]"
                    original = vf.content or ""
                    if task.placeholder in original:
                        vf.content = original.replace(task.placeholder, placeholder_text)
                    else:
                        vf.content = f"{original}\n{placeholder_text}"
                
                drafting_ctx.add_section(task.title, error_msg, success=False)

        # [FIX] Fail-Safe Check
        # Instead of raising Exception (which discards data), we log and mark the workspace error.
        if len(errors) > (total_tasks / 2):
            summary = "; ".join(errors[:3])
            if len(errors) > 3:
                summary += f" ... (+{len(errors)-3} more)"
            
            # Log the critical failure but DO NOT raise.
            # Allowing the workflow to proceed allows the user to see the generated files (even if broken).
            err_msg = f"Critical Drafting Failure: {len(errors)}/{total_tasks} sections failed. Errors: {summary}"
            logger.error(err_msg)
            
            if project_id and node_id:
                await self._emit(project_id, node_id, {"type": "error", "content": err_msg})
                
            # Set workspace flags via side-effect if possible, or rely on caller to notice logs
            # Since this method modifies `workspace` in-place, the errors are already embedded in the files.

        if errors:
            logger.warning(f"Drafting pipeline finished with {len(errors)} partial failures.")

    async def sync_and_compile(
        self,
        project_id: str,
        workspace: PaperWorkspace,
        user_edits: Dict[str, str],
        intent: str,
        event_bus: Optional[EventBus] = None,
        node_id: Optional[str] = None,
        timeout: int = settings.SANDBOX_EXECUTION_TIMEOUT,
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        dormant_assets: Dict[str, str] = None  # [NEW] JIT assets
    ) -> PaperWorkspace:
        """
        Hot Reload & Execution Routing.
        intent="compile" -> Fast Path (execute_fast_compile)
        intent="auto_fix"/"refine" -> Agent Path (delegate_autonomous_fix)
        
        [FIX] Artifact-First Error Handling.
        Returns the workspace with updated content/logs even if the infrastructure crashes.
        """
        self.bus = event_bus or self.bus

        try:
            # 1. Apply Local Edits (Memory Update)
            for path, content in user_edits.items():
                if path in workspace.files:
                    workspace.files[path].content = content

            # 2. Sync to Sandbox
            # [FIX] Resolve BYOK Key for Session Reuse
            e2b_key = runtime.e2b_api_key if (runtime and runtime.e2b_api_key) else settings.E2B_API_KEY
            sb = await self.sandbox.get_active_session(project_id, api_key=e2b_key)
            if not sb:
                # If session died, restart it
                asset_manifest = {
                    p: f.blob_hash for p, f in workspace.files.items()
                    if f.file_type == FileType.ASSET and f.blob_hash
                }
                sb = await self.sandbox.start_agentic_session(project_id, "paper-engine", runtime=runtime, context_manifest=asset_manifest)  # [BYOK]

            await self.sync.push_workspace(sb, workspace)
            
            # 3. JIT Asset Injection (The Fix)
            if dormant_assets:
                # Scan remote .tex files to find references
                from app.core.config import settings
                work_dir = settings.SANDBOX_DATA_DIR
                find_cmd = await sb.commands.run(f"find {work_dir} -name '*.tex'")
                tex_paths = [p.strip() for p in find_cmd.stdout.splitlines() if p.strip()]
                
                full_tex_content = ""
                for p in tex_paths:
                    try:
                        content = await sb.files.read(p)
                        full_tex_content += content + "\n"
                    except Exception as e:
                        logger.warning(f"Failed to read {p}: {e}")
                
                # Regex matches \includegraphics[options]{filename}
                refs = re.findall(r'\\includegraphics(?:\[.*?\])?\{(.*?)\}', full_tex_content)
                
                jit_manifest = {}
                for ref in refs:
                    # Match virtual path or basename
                    if ref in dormant_assets:
                        jit_manifest[ref] = dormant_assets[ref]
                    else:
                        # Try mapping basename "plot.png" -> "history/2.3/plot.png"
                        ref_name = ref.split("/")[-1]
                        for d_path, d_hash in dormant_assets.items():
                            if d_path.endswith(ref_name):
                                jit_manifest[d_path] = d_hash
                                break
                
                if jit_manifest:
                    logger.info(f"JIT: Injecting {len(jit_manifest)} dormant assets referenced in LaTeX.")
                    # SandboxGateway handles chunking automatically if payload > 50MB
                    await self.sandbox.sync_manifest(sb, jit_manifest, is_new_session=False)

            # 4. Route Execution Strategy
            if intent == "compile":
                # STRATEGY A: Fast Compile (Python Script)
                # Cheap, fast, deterministic.
                msg = "Fast Compile: Running build.py..."
                await self._emit(project_id, node_id, {"type": "thought", "content": msg})
                iterator = self.agent.execute_fast_compile(sb, workspace)

            else:
                # STRATEGY B: Autonomous Agent (LLM Driven)
                # Expensive, slow, powerful. Can fix broken LaTeX syntax.
                msg = "Auto Fix: Delegating to Agentic Engineer... (This may take a minute)"
                await self._emit(project_id, node_id, {"type": "thought", "content": msg})
                iterator = self.agent.delegate_autonomous_fix(sb, workspace, timeout=timeout, runtime=runtime)  # [BYOK]

            # 5. Stream & Wait
            async for log in iterator:
                await self._emit(project_id, node_id, log)

            # 6. Pull Result (Logs + PDF)
            ws = await self.sync.pull_snapshot(sb, workspace)
            return ws

        except Exception as e:
            logger.error(f"Sync/Compile Panic: {e}", exc_info=True)
            workspace.compile_status = CompileStatus.ERROR
            err_msg = f"\n[System Error] Operation failed: {str(e)}"
            workspace.last_build_log += err_msg
            
            if project_id and node_id:
                await self._emit(project_id, node_id, {"type": "error", "content": err_msg})

            # Return the workspace as-is (with local edits applied).
            # This ensures user edits are not lost even if the backend crashes.
            return workspace

    async def apply_modification(
        self,
        project_id: str,
        workspace: PaperWorkspace,
        modification_instruction: str,
        target_file: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        node_id: Optional[str] = None,
        timeout: int = settings.SANDBOX_EXECUTION_TIMEOUT,
        runtime: Optional[RuntimeConfig] = None  # [BYOK]
    ) -> PaperWorkspace:
        """
        [AI-Assisted Modification]
        Applies user-requested modifications to the paper using AI.
        
        Args:
            project_id: Project identifier
            workspace: Current paper workspace
            modification_instruction: User's modification request
            target_file: Specific file to modify (None = auto-detect)
            event_bus: Optional event bus
            node_id: Node ID for logging
            timeout: Execution timeout
            runtime: Runtime config
        
        Returns:
            Updated workspace with modifications
        """
        self.bus = event_bus or self.bus

        try:
            # 1. Ensure we have an active sandbox session
            e2b_key = runtime.e2b_api_key if (runtime and runtime.e2b_api_key) else settings.E2B_API_KEY
            sb = await self.sandbox.get_active_session(project_id, api_key=e2b_key)
            if not sb:
                asset_manifest = {
                    p: f.blob_hash for p, f in workspace.files.items()
                    if f.file_type == FileType.ASSET and f.blob_hash
                }
                sb = await self.sandbox.start_agentic_session(
                    project_id, "paper-engine", runtime=runtime, context_manifest=asset_manifest
                )

            # 2. Sync workspace to sandbox first
            await self.sync.push_workspace(sb, workspace)

            # 3. Apply modification via BuildAgent
            iterator = self.agent.apply_user_modification(
                sb, workspace, modification_instruction, 
                target_file=target_file, timeout=timeout, runtime=runtime
            )

            # 4. Stream progress
            async for log in iterator:
                await self._emit(project_id, node_id, log)

            # 5. Pull updated workspace
            ws = await self.sync.pull_snapshot(sb, workspace)
            return ws

        except Exception as e:
            logger.error(f"Modification failed: {e}", exc_info=True)
            workspace.compile_status = CompileStatus.ERROR
            err_msg = f"\n[Modification Error] {str(e)}"
            workspace.last_build_log += err_msg
            
            if project_id and node_id:
                await self._emit(project_id, node_id, {"type": "error", "content": err_msg})

            return workspace

    def _physicalize_text(self, text: str, asset_map: Dict[str, str]) -> str:
        """
        Replaces virtual paths (history/2.3/plot.png) with physical filenames (fig_01.png).
        Helper logic borrowed from PromptFactory but applied locally for Paper Engine.
        """
        if not text or not asset_map:
            return text
        
        # Sort by length descending to prevent partial matches
        sorted_map = sorted(asset_map.items(), key=lambda x: len(x[0]), reverse=True)
        
        result = text
        for v_path, p_path in sorted_map:
            result = result.replace(v_path, p_path)
            
        return result

    async def _emit(self, pid: Optional[str], nid: Optional[str], log: Dict[str, Any]):
        if self.bus and pid and nid:
            content = log.get("content", "")
            log_type = log.get("type", "info")
            
            # Determine tag based on log type
            if log_type == "error":
                tag = SystemTags.STDERR
            elif log_type == "thought":
                tag = SystemTags.THOUGHT
            elif log_type == "warning":
                tag = SystemTags.STDERR  # Use STDERR for warnings to stand out
            elif log_type == "status":
                # [NEW] Status messages for real-time compile feedback
                # Extract stage info if present
                stage = log.get("stage", "")
                status_content = log.get("content", "")
                if stage and status_content:
                    # Format: "STATUS: {stage} - {content}"
                    content = f"[{stage.upper()}] {status_content}"
                tag = SystemTags.EXECUTION_LOGS
            else:
                tag = SystemTags.EXECUTION_LOGS
                
            await self.bus.publish(
                f"project:{pid}",
                "EXEC_LOG",
                {"node_id": nid, "content": content, "stream": tag}
            )
