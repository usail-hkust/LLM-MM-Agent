"""
Node Processor - The Engine.

[Updated]
- Implemented Global Asset Registration (Fix for 404s).
- Implemented Identity Inheritance (Semantic ID Reconciler).
- Fixed 'Execute Only' to use previous output as template.
- Enhanced Metadata stability.
- [FIX] Adaptive Sampling: Auto-enable batching for SCA nodes on first run.
- [MODIFIED] Increased SCA default batch size to 6.
- [CRITICAL FIX] Updated Error Block Extraction to match SandboxGateway labels ("Console Errors").
- [CRITICAL FIX] ID Assurance: Ensure every block has a UUIDv4 before persistence.
- [REFACTOR] Strict Pipeline Routing: Agentic vs Native vs Generator.
- [REFACTOR] Removed StandardOutputParser dependency for Executor nodes.
- [REFACTOR] Removed legacy "Executor Pause" logic (replaced by Agentic Loop).
- [REFACTOR] Maintained Identity Persistence and View Hydration.
- [FIX] Added Markdown Consolidation for MARKDOWN_VIEWER nodes to prevent block fragmentation.
- [FIX] Enhanced Agentic Output Hydration: Now explicitly hydrates .txt/.md/.csv/.json files as visible blocks.
- [FIX] 3.1 Outline Post-Processing: Preserve Dictionary Structure for Frontend SCA Card compatibility.
"""
import logging
import re
import json
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
from datetime import datetime
from uuid import uuid4, UUID # [FIX] Ensure import

from app.core.config import settings
from app.core.definitions import NodeType, BlockType, SystemTags, RenderType
from app.core.events import EventBus
from app.core.exceptions import ExecutionError
from app.domain.blueprints import NodeBlueprint
from app.domain.unified_io import NodeOutput, ContentBlock
from app.infra.gateways.llm import LLMGateway
from app.infra.gateways.sandbox import SandboxGateway
from app.infra.asset_manager import AssetManager
from app.infra.file_parsers import FileETL
from app.infra.persistence.database import AsyncSessionLocal
from app.utils.files import guess_mime_type, ensure_dir # [FIX] Add guess_mime_type
from app.services.prompt_factory import PromptFactory
from app.paper_engine import PaperEngineManager, PaperWorkspace
from app.paper_engine.domain import VirtualFile, FileType, CompileStatus
from app.paper_engine.asset_pipeline import AssetPipeline
from app.api.schemas import RuntimeConfig

logger = logging.getLogger(__name__)


class NodeProcessor:
    """
    [Stateless Worker]
    Orchestrates the execution pipeline with Identity Persistence.
    
    Architecture:
    - Route 1 (Agentic): Executor nodes with agentic_claude engine use Agentic Loop
      to directly execute in sandbox, harvesting artifacts from filesystem.
      Bypasses StandardOutputParser completely.
    
    - Route 2 (Native): Specialized executors (e.g., native_paper_engine) use
      dedicated managers. Also bypasses StandardOutputParser.
    
    - Route 3 (Generator): Generator nodes use LLM text generation with
      StandardOutputParser to extract structured JSON/Markdown outputs.
      This is the ONLY path where StandardOutputParser is used.
    
    Key Design Principles:
    - Executor nodes NEVER use StandardOutputParser (they use Artifact Harvesting)
    - Generator nodes ALWAYS use StandardOutputParser (they produce structured text)
    - Legacy "Executor Pause" logic has been removed (replaced by Agentic Loop)
    """

    def __init__(
        self,
        llm: LLMGateway,
        sandbox: SandboxGateway,
        assets: AssetManager,
        prompts: PromptFactory,
        paper_manager: PaperEngineManager,
        event_bus: Optional[EventBus] = None
    ):
        self.llm = llm
        self.sandbox = sandbox
        self.assets = assets
        self.prompts = prompts
        self.paper_manager = paper_manager
        self.bus = event_bus
        from app.infra.persistence.repositories import ProjectRepository
        self.p_repo = ProjectRepository()

    async def _hydrate_mcm_template_scaffold(
        self, 
        meta: Dict[str, Any], 
        outline: List[str]
    ) -> Dict[str, bytes]:
        """
        [NEW] Core Method: Standard MCM Template Hydration.
        1. Loads standard template from `app/templates/MCM`.
        2. Injects metadata into `main.tex`.
        3. [CRITICAL] Removes all bibliography/citation commands to meet requirement.
        4. Generates scaffolding for `part_X.tex` based on outline.
        
        Returns: Map of {filename: content_bytes}
        """
        # Resolve path relative to this file: services/node_processor.py -> app/ -> ...
        backend_dir = Path(__file__).resolve().parent.parent.parent
        template_dir = backend_dir / settings.TEMPLATE_ROOT / "MCM"
        
        if not template_dir.exists():
            logger.error(f"MCM Template dir missing: {template_dir}")
            return {}

        generated_assets = {} 

        # 1. Process Static Assets (Images, styles, existing tex)
        # Skip special files we will regenerate
        skip_list = ["main.tex", "part_4_Appendix.tex", "part_1_pre.tex", "part_2_model.tex", "part_3_conclusion.tex"]
        
        for fpath in template_dir.glob("**/*"):
            if fpath.is_dir(): continue
            rel_path = fpath.relative_to(template_dir).as_posix()
            
            # Skip build artifacts
            if rel_path.endswith(('.aux', '.log', '.out', '.gz', '.fls', '.fdb_latexmk', 'main.pdf')):
                continue
            
            if rel_path in skip_list:
                continue
                
            generated_assets[rel_path] = fpath.read_bytes()

        # 2. Process main.tex (Metadata Injection & Citation Stripping)
        main_tex_path = template_dir / "main.tex"
        if main_tex_path.exists():
            content = main_tex_path.read_text(encoding="utf-8")
            
            # [Metadata Injection]
            ctl = str(meta.get("control_number", "0000000"))
            content = re.sub(r"\\usepackage\[.*?\]\{easymcm\}", f"\\\\usepackage[{ctl}]{{easymcm}}", content)
            
            pid = str(meta.get("problem_id", "A"))
            content = re.sub(r"\\problem\{.*?\}", f"\\\\problem{{{pid}}}", content)
            
            title = str(meta.get("title", "MCM Modeling Report"))
            # Replace placeholder or standard title command
            if "Input Your Article Title Here" in content:
                content = content.replace(r"Input Your Article Title Here \\ if it is too Long", title)
            else:
                content = re.sub(r"\\title\{[^}]*\}", f"\\\\title{{{title}}}", content)
            
            # [CRITICAL REQUIREMENT] Remove Citation Logic
            content = re.sub(r"\\bibliographystyle\{.*?\}", "", content)
            content = re.sub(r"\\bibliography\{.*?\}", "", content)
            content = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "", content, flags=re.DOTALL)
            
            generated_assets["main.tex"] = content.encode("utf-8")

        # 3. Process Appendix (Reset & Strip Citations)
        # We start fresh to ensure no residual bib commands
        app_path = template_dir / "part_4_Appendix.tex"
        if app_path.exists():
            content = (
                "\\newpage\n"
                "\\appendix\n"
                "\\section{Code and Memos}\n"
                "% Code will be automatically appended here.\n"
                "% Note: No bibliography section per requirements.\n"
            )
            generated_assets["part_4_Appendix.tex"] = content.encode("utf-8")

        # 4. Smart Scaffolding (Parts 1-3)
        # Distribute outline sections to appropriate files
        sections_map = {
            "part_1_pre.tex": [],
            "part_2_model.tex": [],
            "part_3_conclusion.tex": []
        }
        
        for section in outline:
            # Clean "1. Title" -> "Title"
            clean_title = re.sub(r"^\d+(\.\d+)*\s*", "", str(section)).strip()
            if not clean_title: continue
            
            s_lower = clean_title.lower()
            
            if any(kw in s_lower for kw in ["introduction", "background", "restatement", "assumption", "notation", "data"]):
                sections_map["part_1_pre.tex"].append(clean_title)
            elif any(kw in s_lower for kw in ["sensitivity", "strength", "weakness", "evaluate", "conclusion", "discussion", "future"]):
                sections_map["part_3_conclusion.tex"].append(clean_title)
            else:
                # Core modeling goes to Part 2
                sections_map["part_2_model.tex"].append(clean_title)

        # Generate structural files
        for fname, titles in sections_map.items():
            file_content = f"% {fname} - Auto-generated Scaffolding\n"
            if not titles:
                file_content += "% No specific sections assigned to this part yet.\n"
            
            for title in titles:
                file_content += f"\\section{{{title}}}\n% TODO: Write detailed content for {title} here.\n\n"
            
            generated_assets[fname] = file_content.encode("utf-8")

        return generated_assets

    async def process(
        self,
        project_id: str,
        blueprint: NodeBlueprint,
        context_str: str,
        file_manifest: Dict[str, str],
        user_input: Dict[str, Any],
        intent: str = "generate",
        config: Dict[str, Any] = None,
        previous_output: Optional[NodeOutput] = None,
        file_schemas: Dict[str, List[str]] = None,  # [NEW] Accept schemas
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        dormant_manifest: Dict[str, str] = None  # [NEW]
    ) -> List[NodeOutput]:
        """
        Executes the logic defined in the NodeBlueprint.
        Strictly routes based on Node Type and Executor Engine.
        
        Architecture:
        1. Route 1: Agentic Execution Pipeline (Executor Nodes with agentic_claude)
        2. Route 2: Native Engine Pipeline (Specialized Executors like native_paper_engine)
        3. Route 3: Structured Generation Pipeline (Generator Nodes, uses StandardOutputParser)
        """
        start_time = datetime.utcnow()
        config = config or {}
        engine = blueprint.meta.get("executor_engine")
        inputs = user_input.get("inputs", {})
        outputs: List[NodeOutput] = []
        is_sca_node = bool(blueprint.interaction and blueprint.interaction.can_select_alternatives)

        # --- [FIX START] Global Asset Layout Resolution ---
        # Determine exact physical filenames for Prompt & Sandbox.
        # This solves the "Triple Fracture" by creating a single source of truth.
        asset_map = None  # Mapping: VirtualPath -> CanonicalPhysicalPath
        sandbox_layout = None  # Mapping: CanonicalPhysicalPath -> BlobHash

        # Strategy: Ledger Look-Ahead (Only for Reporting Phase)
        # Resolve Layout (Active + Dormant for full paths)
        if blueprint.phase_label and "Reporting" in blueprint.phase_label:
            full_manifest = {**file_manifest, **(dormant_manifest or {})}
            sandbox_layout, asset_map = await self._resolve_asset_layout(project_id, full_manifest)
        # --- [FIX END] ---

        # =========================================================================
        # ROUTE 1: AGENTIC EXECUTION PIPELINE (Executor Nodes)
        # Bypasses StandardOutputParser completely.
        # =========================================================================
        if engine == "agentic_claude":
            # 1.1 Agentic Auto-Fix / Generate Loop
            if intent in ["generate", "refine"]:
                logger.info(f"Routing Node {blueprint.id} to Agentic Workflow (Intent: {intent})")
                outputs = await self._run_agentic_loop(
                    project_id,
                    blueprint,
                    context_str,
                    sandbox_layout if sandbox_layout else file_manifest,
                    user_input,
                    intent,
                    start_time,
                    timeout=config.get("timeout", settings.DEFAULT_AGENT_TIMEOUT),
                    asset_map=asset_map,
                    runtime=runtime  # [BYOK]
                )
            
            # 1.2 Interactive Execution (Fast Path)
            elif intent == "execute_only":
                logger.info(f"Routing Node {blueprint.id} to Interactive Execution (Intent: {intent})")
                outputs = await self._run_interactive_mode(
                    project_id,
                    user_input,
                    sandbox_layout if sandbox_layout else file_manifest,
                    previous_output,
                    start_time,
                    asset_map=asset_map,
                    runtime=runtime  # [BYOK]
                )

        # =========================================================================
        # ROUTE 2: NATIVE ENGINE PIPELINE (Specialized Executors)
        # Bypasses StandardOutputParser completely.
        # =========================================================================
        elif engine == "native_paper_engine":
            logger.info(f"Routing Node {blueprint.id} to Paper Engine v3 (Intent: {intent})")
            # Need to split sandbox_layout back into active/dormant physical mappings
            active_layout = {}
            dormant_layout = {}
            if sandbox_layout:
                from app.utils.files import is_visual_asset
                for p_path, blob in sandbox_layout.items():
                    if is_visual_asset(p_path):
                        dormant_layout[p_path] = blob
                    else:
                        active_layout[p_path] = blob
            else:
                active_layout = file_manifest
                dormant_layout = dormant_manifest or {}
            
            outputs = await self._run_paper_engine(
                project_id,
                blueprint,
                context_str,
                active_layout,  # Only sync active files initially
                inputs,
                user_input,
                intent,
                previous_output,
                start_time,
                config=config,
                runtime=runtime,  # [BYOK]
                asset_map=asset_map,  # [FIX] Pass asset_map
                sandbox_layout=sandbox_layout,  # [FIX] Pass sandbox_layout
                dormant_manifest=dormant_layout  # [FIX] Pass JIT assets
            )
        
        # Guard: Unknown engine
        elif engine:
            logger.warning(f"Unknown engine '{engine}' for node {blueprint.id}. Returning error.")
            native_output = NodeOutput(
                blocks=[ContentBlock(
                    type=BlockType.MARKDOWN, 
                    label="System Error", 
                    content=f"Configuration Error: Unknown executor engine '{engine}'"
                )],
                metadata={"exit_code": 1}
            )
            self._ensure_ids(native_output)
            saved = await self.assets.process_and_save(native_output)
            self._enrich_metadata(saved, start_time, mode="error")
            outputs = [saved]

        if not engine and intent == "execute_only":
            raise ValueError(f"Execute-only is not supported for node {blueprint.id} without an agentic or native executor.")

        # =========================================================================
        # ROUTE 3: STRUCTURED GENERATION PIPELINE (Generator Nodes)
        # Uses StandardOutputParser to extract JSON/Markdown.
        # =========================================================================
        if not engine:
            # [Safety Check] Executors must not fall through to text generation in v3
            if blueprint.node_type == NodeType.EXECUTOR:
                logger.error(f"Executor Node {blueprint.id} lacks 'executor_engine' config. Falling back to text generation (Legacy Mode).")
                # We allow fallback but log error, or strictly raise exception. 
                # For backward compatibility with misconfigured blueprints, we proceed but log heavily.

            logger.info(f"Processing Node {blueprint.id} in STANDARD GENERATION mode")
            
            # 1. Determine Sample Count (Adaptive Sampling)
            default_samples = 1
            
            if intent == "generate":
                if is_sca_node:
                    default_samples = 6  # [CHANGED] Default batch for SCA increased to 6
                default_samples = config.get("num_samples", default_samples)
            elif intent == "refine":
                if is_sca_node:
                    default_samples = config.get("num_samples", 6) # [CHANGED] Keep consistent
                else:
                    default_samples = config.get("num_samples", 1)
            
            # [CHANGED] Increased cap to 10 to allow 6 samples
            num_samples = max(1, min(default_samples, 10))

            # 2. Render Prompt with Batch Configuration
            try:
                messages = self.prompts.create_messages(
                    blueprint, intent, context_str, file_manifest, user_input, previous_output,
                    file_schemas=file_schemas,
                    num_samples=num_samples,  # [NEW] Pass batch size to PromptFactory
                    asset_map=asset_map
                )
            except Exception as e:
                raise ExecutionError("Prompt Rendering", str(e))

            # 3. Single-Pass Generation
            logger.info(f"SPDG: Generating {num_samples} options in a SINGLE call for {blueprint.id}")
            
            try:
                raw_output = await self.llm.generate_raw(
                    messages, 
                    temperature=config.get("temperature", 0.7),
                    node_id=blueprint.id,
                    runtime=runtime  # [BYOK]
                )
            except Exception as e:
                raise ExecutionError("LLM", f"Generation failed: {str(e)}")

            # 4. Parsing (The only place StandardOutputParser is used)
            target_label = blueprint.output_spec.target_label if blueprint.output_spec else None
            valid_outputs = []
            
            if num_samples > 1 and target_label:
                valid_outputs = self.llm.parser.parse_batch(raw_output, target_label)
                logger.info(f"SPDG: Split single response into {len(valid_outputs)} distinct options.")
                
                if not valid_outputs:
                    logger.warning("SPDG Split failed (Anchor not found). Returning raw output as single option.")
                    valid_outputs = [self.llm.parser.parse(raw_output)]
            else:
                valid_outputs = [self.llm.parser.parse(raw_output)]

            if not valid_outputs:
                raise ExecutionError("LLM", "All generation attempts failed.")

            # [FIX] Consolidate blocks for Markdown Viewer
            # If the node is configured as a Markdown Viewer, force all blocks into a single
            # consolidated Markdown block to prevent UI fragmentation.
            if blueprint.ux.primary_view == RenderType.MARKDOWN_VIEWER:
                for output in valid_outputs:
                    self._consolidate_output_for_markdown_view(output)

            # 5. Identity Reconcile & ID Assurance
            self._reconcile_identities(valid_outputs, previous_output)
            for output in valid_outputs:
                self._ensure_ids(output)

            # [REMOVED] Legacy "Executor Pause" logic was here. 
            # Since Executors route via Agentic Loop, we no longer need to pause purely text-generated code.

            # 6. Post-Processing & Persistence
            processed_outputs = []
            for output in valid_outputs:
                # Check for LLM Failure (e.g. JSON parse error flagged in parser)
                if output.metadata.get("exit_code", 0) != 0:
                    self._enrich_metadata(output, start_time)
                    processed_outputs.append(output)
                    continue

                # Hook: Outline normalization
                if blueprint.id == "3.1":
                    self._post_process_outline(output)

                # Persist binaries (Final Pass)
                saved = await self.assets.process_and_save(output)
                self._enrich_metadata(saved, start_time)
                processed_outputs.append(saved)

            outputs = processed_outputs

        # === [FIX] GLOBAL ASSET REGISTRATION ===
        new_assets_map: Dict[str, str] = {}
        for output in outputs:
            queue = list(output.blocks)
            while queue:
                block = queue.pop(0)
                if block.children:
                    queue.extend(block.children)

                if block.type != BlockType.FILE:
                    continue

                blob_hash = block.meta.get("blob_hash")
                filename = block.meta.get("filename", block.label)
                if not blob_hash or not filename:
                    continue

                v_path = block.meta.get("virtual_path")
                if not v_path:
                    if "/" in filename:
                        v_path = filename
                    else:
                        v_path = f"history/{blueprint.id}/{filename}"
                    block.meta["virtual_path"] = v_path

                new_assets_map[v_path] = blob_hash

        if new_assets_map:
            try:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        project = await self.p_repo.get(project_id, session=session)
                        if project:
                            project.assets.update(new_assets_map)
                            await self.p_repo.save(project, session=session)
                logger.info(f"Registered {len(new_assets_map)} assets for node {blueprint.id}")
            except Exception as e:
                logger.error(f"Failed to register assets: {e}")

        # 7. Default Selection Logic
        if outputs and not any(o.is_selected for o in outputs):
            if not is_sca_node:
                # Linear flow: Auto-select HEAD
                outputs[-1].is_selected = True
            else:
                # SCA flow: Explicitly ensure none are selected
                for o in outputs:
                    o.is_selected = False

        return outputs

    # =========================================================================
    # INTERNAL HANDLERS
    # =========================================================================

    async def _resolve_asset_layout(
        self,
        project_id: str,
        manifest: Dict[str, str]
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Calculates Stable Physical Filenames using AssetLedger.
        Returns: (sandbox_layout, asset_map)
        """
        if not manifest:
            return {}, {}

        logger.info("Resolving assets via AssetLedger for Reporting Phase")
        try:
            pid = project_id if isinstance(project_id, UUID) else UUID(project_id)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    project = await self.p_repo.get(pid, session=session)
                    if project:
                        # [FIX] Use prepare_assets_for_sandbox for correct format
                        pipeline = AssetPipeline(self.assets)
                        sandbox_layout, asset_map = await pipeline.prepare_assets_for_sandbox(project, manifest)

                        # Persist Ledger Update Immediately
                        await self.p_repo.save(project, session=session)
                        return sandbox_layout, asset_map
        except Exception as e:
            logger.error(f"Asset resolution failed: {e}", exc_info=True)

        return {}, {}

    def _consolidate_output_for_markdown_view(self, output: NodeOutput):
        """
        [FIX] Consolidates all blocks into a single MARKDOWN block.
        Ensures continuous document rendering for primary_view=MARKDOWN_VIEWER.
        Reconstructs fenced code blocks into the markdown stream.
        """
        if not output.blocks:
            return

        # Optimization: If already single markdown block, skip
        if len(output.blocks) == 1 and output.blocks[0].type == BlockType.MARKDOWN:
            return

        merged_parts = []

        for block in output.blocks:
            content = block.content
            if content is None: 
                continue
            
            text_chunk = ""
            
            # Reconstruct Fences for structured blocks
            if block.type == BlockType.CODE:
                lang = block.meta.get("language", "")
                text_chunk = f"```{lang}\n{str(content)}\n```"
            
            elif block.type == BlockType.DATA:
                try:
                    if isinstance(content, (dict, list)):
                        json_str = json.dumps(content, indent=2, ensure_ascii=False)
                        text_chunk = f"```json\n{json_str}\n```"
                    else:
                        text_chunk = str(content)
                except:
                    text_chunk = str(content)
            
            # For File blocks (from parser text-fencing), keep as text representation
            elif block.type == BlockType.FILE:
                # Only if it hasn't been processed to binary yet (which it hasn't at this stage in Route 3)
                filename = block.meta.get("filename") or block.label
                text_chunk = f"```file:{filename}\n{str(content)}\n```"

            else:
                # Markdown and others
                text_chunk = str(content)
            
            merged_parts.append(text_chunk)

        full_text = "\n\n".join(merged_parts)
        
        # Replace with single consolidated block
        output.blocks = [
            ContentBlock(
                type=BlockType.MARKDOWN,
                label=output.blocks[0].label or "Document", # Preserve first label or generic
                content=full_text,
                tags=["consolidated"]
            )
        ]

    async def _run_paper_engine(
        self,
        project_id: str,
        blueprint: NodeBlueprint,
        context_str: str,
        file_manifest: Dict[str, str],
        inputs: Dict[str, Any],
        user_input: Dict[str, Any],
        intent: str,
        previous_output: Optional[NodeOutput],
        start_time: datetime,
        config: Dict[str, Any],
        runtime: Optional[RuntimeConfig] = None,  # [BYOK]
        asset_map: Optional[Dict[str, str]] = None,  # [FIX] Virtual -> Physical
        sandbox_layout: Optional[Dict[str, str]] = None,  # [FIX] Physical -> Hash
        dormant_manifest: Dict[str, str] = None  # [NEW]
    ) -> List[NodeOutput]:
        """Helper to run the Native Paper Engine logic."""
        workspace = None

        # Rehydrate Workspace from previous state
        if previous_output:
            ws_block = previous_output.get_block("workspace_state")
            if ws_block and ws_block.meta.get("full_state"):
                try:
                    workspace = PaperWorkspace.model_validate(ws_block.meta["full_state"])
                except Exception as exc:
                    logger.warning(f"Workspace rehydrate failed: {exc}")
            elif ws_block and ws_block.content and isinstance(ws_block.content, dict):
                # Legacy fallback
                workspace = PaperWorkspace(project_id=project_id)
                for path, entry in ws_block.content.items():
                    if not isinstance(entry, dict): continue
                    ftype = entry.get("type")
                    try:
                        ftype_enum = FileType(ftype) if ftype else FileType.LATEX_PART
                    except Exception:
                        ftype_enum = FileType.LATEX_PART
                    workspace.files[path] = VirtualFile(
                        path=path,
                        content=entry.get("content"),
                        blob_hash=entry.get("blob_hash"),
                        file_type=ftype_enum,
                        is_readonly=bool(entry.get("readonly", False)),
                    )

        if intent == "generate":
            # Initialize Workspace Logic
            outline = inputs.get("outline")
            symbol_table = inputs.get("symbol_table")

            # Fallback extraction logic
            if isinstance(outline, dict) and symbol_table is None:
                symbol_table = outline.get("symbol_table") or outline.get("symbols")

            if not outline and inputs.get("selected_option_content"):
                sel = inputs.get("selected_option_content")
                if isinstance(sel, dict):
                    outline = sel.get("outline") or sel.get("structure")
                    if symbol_table is None:
                        symbol_table = sel.get("symbol_table")

            if (not outline or symbol_table is None) and previous_output:
                blk = (
                    previous_output.get_block("paper_blueprint")
                    or previous_output.get_block("paper_plan")
                    or previous_output.get_block("outline")
                    or previous_output.get_block("json")
                )
                if blk:
                    if isinstance(blk.content, dict):
                        if not outline:
                            outline = blk.content.get("outline") or blk.content.get("structure")
                        if symbol_table is None:
                            symbol_table = blk.content.get("symbol_table") or blk.content.get("symbols")
                    elif not outline:
                        outline = blk.content

            outline = self._coerce_outline(outline)
            if not outline:
                logger.warning("No outline found for Paper Engine. Using fallback.")
                outline = ["1. Introduction", "2. Data", "3. Model", "4. Results", "5. Conclusion"]

            meta = {
                "title": inputs.get("title", "MCM Modeling Report"),
                "problem_id": inputs.get("problem_id", "A"),
                "control_number": inputs.get("control_number", "0000000"),
                "symbol_table": symbol_table or {},
            }
            
            # [FIX START] MCM Template Scaffolding Injection
            if blueprint.meta.get("template_mode") == "MCM_STANDARD" or blueprint.id == "3.2":
                logger.info("Injecting MCM Standard Template Scaffolding (No Citations)...")
                
                # 1. Generate scaffold content
                scaffold_files = await self._hydrate_mcm_template_scaffold(meta, outline)
                
                # 2. Register to CAS
                scaffold_manifest = {}
                for fname, content in scaffold_files.items():
                    blob_hash = await self.assets.save_bytes(content)
                    scaffold_manifest[fname] = blob_hash
                
                # 3. Merge into Sandbox Layout (Template overwrites anything else)
                if sandbox_layout is None:
                    sandbox_layout = {}
                sandbox_layout.update(scaffold_manifest)
                
                # 4. Update logical manifest
                file_manifest.update(scaffold_manifest)
            # [FIX END]

            # [FIX] Extract User Instruction for Section Writer
            # Priority: explicit 'instruction' in command -> 'user_instruction' in inputs
            user_instruction = inputs.get("instruction") or user_input.get("instruction") or ""
            
            # [REFACTORED] Pass config for timeout control
            agent_timeout = config.get("timeout", settings.DEFAULT_AGENT_TIMEOUT)
            
            # [FIX] Ensure asset layout is resolved if not passed
            if not asset_map or not sandbox_layout:
                if blueprint.phase_label and "Reporting" in blueprint.phase_label:
                    sandbox_layout, asset_map = await self._resolve_asset_layout(project_id, file_manifest)
            
            workspace = await self.paper_manager.initialize_workspace(
                project_id,
                outline,
                file_manifest,  # Active only
                meta,
                context_str=context_str,
                event_bus=self.bus,
                node_id=blueprint.id,
                timeout=agent_timeout,  # [NEW] Pass boundary
                runtime=runtime,  # [BYOK] Pass runtime for BYOK support
                asset_map=asset_map,  # [FIX] Pass Resolved Maps
                sandbox_layout=sandbox_layout,  # [FIX] Pass Resolved Maps
                instruction=user_instruction  # [FIX] Pass instruction
            )
            
            # Trigger immediate compile to fill content + JIT assets
            workspace = await self.paper_manager.sync_and_compile(
                project_id, workspace, {}, "compile", self.bus, blueprint.id,
                config.get("timeout", 300), runtime, dormant_assets=dormant_manifest
            )

        elif intent in ["compile", "refine", "auto_fix"]:
            if not workspace:
                workspace = PaperWorkspace(project_id=project_id)
            user_edits = dict(inputs.get("modified_files", {}))

            manual_content = user_input.get("manual_content") or inputs.get("manual_content")
            active_block_id = user_input.get("block_id") or inputs.get("block_id")

            if manual_content is not None:
                if isinstance(manual_content, dict):
                    logger.info(f"PaperEngine: Detected workspace object ({len(manual_content)} files).")
                    for path, file_node in manual_content.items():
                        if isinstance(file_node, dict) and "content" in file_node:
                            content_val = file_node.get("content")
                            if isinstance(content_val, str):
                                user_edits[path] = content_val
                        elif isinstance(file_node, str):
                            user_edits[path] = file_node
                elif isinstance(manual_content, str) and active_block_id:
                    file_path = active_block_id
                    if file_path.startswith("file:"): file_path = file_path[5:]
                    elif file_path.startswith("path:"): file_path = file_path[5:]

                    if "." in file_path or "/" in file_path:
                        user_edits[file_path] = manual_content
                    else:
                        logger.warning(f"Ignored manual content for unresolvable key: {file_path}")

            mgr_intent = "auto_fix" if intent in ["refine", "auto_fix"] else "compile"
            
            # [REFACTORED] Pass config for timeout control
            agent_timeout = config.get("timeout", settings.DEFAULT_AGENT_TIMEOUT)
            
            workspace = await self.paper_manager.sync_and_compile(
                project_id,
                workspace,
                user_edits,
                intent=mgr_intent,
                event_bus=self.bus,
                node_id=blueprint.id,
                timeout=agent_timeout,  # [NEW] Pass boundary
                runtime=runtime,  # [BYOK]
                dormant_assets=dormant_manifest  # [FIX] Pass JIT assets
            )

        else:
            raise ValueError(f"Unknown intent '{intent}' for paper engine.")

        output = self._wrap_paper_output(workspace)
        if previous_output:
            self._reconcile_identities([output], previous_output)
        
        self._ensure_ids(output)
        saved = await self.assets.process_and_save(output)
        self._enrich_metadata(saved, start_time, mode="paper_engine_v3")
        return [saved]

    def _create_file_block(self, filename: str, content_bytes: bytes, blob_hash: str) -> ContentBlock:
        # [FIX] Detect MIME type early
        mime_type = guess_mime_type(filename)
        meta = {
            "filename": filename, 
            "blob_hash": blob_hash,
            "mime_type": mime_type # [NEW] Propagate MIME type
        }

        if filename.lower().endswith((".csv", ".tsv", ".xlsx", ".json")):
            try:
                info = FileETL.inspect(filename, content_bytes)
                if "headers" in info and isinstance(info["headers"], list):
                    meta["schema_columns"] = info["headers"]
                    if "row_count_estimate" in info:
                        meta["row_count_hint"] = info["row_count_estimate"]
            except Exception as e:
                logger.warning(f"Schema sniffing failed for {filename}: {e}")

        return ContentBlock(
            type=BlockType.FILE,
            label=filename,
            content=content_bytes,
            meta=meta
        )

    async def _run_agentic_loop(
        self,
        project_id: str,
        blueprint: NodeBlueprint,
        context_str: str,
        file_manifest: Dict[str, str],
        user_input: Dict[str, Any],
        intent: str,
        start_time: datetime,
        timeout: int,  # [NEW] Mandatory boundary
        asset_map: Optional[Dict[str, str]] = None,
        runtime: Optional[RuntimeConfig] = None  # [BYOK]
    ) -> List[NodeOutput]:
        # 1. Init Environment (Tarball)
        sb = await self.sandbox.start_agentic_session(
            project_id,
            blueprint.id,
            runtime=runtime,  # [BYOK]
            context_manifest=file_manifest if not asset_map else None,
            layout=file_manifest if asset_map else None
        )

        # 2. Generate Prompt
        agent_goal = self.prompts.create_agent_goal(
            blueprint,
            intent,
            context_str,
            user_input,
            file_manifest=file_manifest,
            asset_map=asset_map
        )

        # 3. Run & Stream with Boundary
        logs = []
        exit_code = 0
        
        # [NEW] 发送进度开始事件
        await self._publish_progress(project_id, blueprint.id, "agent_progress_start", {
            "title": f"Running {blueprint.meta.get('display_name', blueprint.id)}",
            "totalSteps": 5
        })
        current_step = 0
        
        # [FIX] Pass timeout to Sandbox
        async for log in self.sandbox.run_agent_cli(sb, agent_goal, timeout=timeout, runtime=runtime):  # [BYOK]
            content = log.get("content", "")
            ltype = log.get("type", "stdout")

            if ltype == "error":
                exit_code = 1

            if self.bus:
                if ltype == "thought":
                    stream_tag = SystemTags.THOUGHT
                elif ltype == "stderr":
                    stream_tag = SystemTags.STDERR
                elif ltype == "error":
                    stream_tag = SystemTags.ERROR
                else:
                    stream_tag = SystemTags.STDOUT

                await self.bus.publish(
                    f"project:{project_id}",
                    "EXEC_LOG",
                    {"node_id": blueprint.id, "content": content, "stream": stream_tag}
                )
                
                # [NEW] 发送进度更新事件（每10条日志或关键步骤）
                if ltype in ["thought", "action"] and content:
                    current_step += 1
                    await self._publish_progress(project_id, blueprint.id, "agent_progress", {
                        "percentage": min(50 + current_step * 5, 80),
                        "message": content[:200],
                        "currentStep": current_step
                    })

            logs.append(f"[{ltype}] {content}")

        # [NEW] 发送进度完成事件
        await self._publish_progress(project_id, blueprint.id, "agent_progress_complete", {
            "message": "Execution completed, harvesting artifacts..."
        })

        # 4. Harvest Artifacts (Diff Sync)
        # [CRITICAL FIX] Prevent Ghost Asset Re-downloading
        # If we filtered 'plot.png' from injection, but it exists in Sandbox (from prev run),
        # Harvest will think it's new because it's not in 'file_manifest'.
        # We must fetch the FULL project state to deduplicate.
        
        full_knowledge_manifest = file_manifest.copy()
        try:
            # Fetch global state to know what ALREADY exists in the project
            from uuid import UUID
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    p = await self.p_repo.get(UUID(project_id), session=session)
                    if p:
                        full_knowledge_manifest.update(p.assets)
        except Exception as e:
            logger.warning(f"Failed to fetch full knowledge for harvest dedup: {e}")

        # Use Full Knowledge for exclusion checks
        normalized_manifest = self._normalize_manifest_paths(full_knowledge_manifest)
        new_files, full_state_map = await self.sandbox.harvest_artifacts_diff(sb, normalized_manifest)

        # 5. [FIX START] Block Categorization & Prioritization
        # Instead of appending to a single list, we bucket them to enforce UI layout order.
        # Priority: Code > Data (Visuals) > Reports (Markdown) > Raw Files
        
        code_blocks: List[ContentBlock] = []
        visual_blocks: List[ContentBlock] = []
        report_blocks: List[ContentBlock] = []
        asset_blocks: List[ContentBlock] = [] # The generic FILE blocks

        for fname, fhash in full_state_map.items():
            if fname in new_files:
                data = new_files[fname]
                
                lower_fname = fname.lower()
                
                # A. Code Files (Highest Priority for Executor Nodes)
                if lower_fname.endswith(".py"):
                    code_blocks.append(ContentBlock(
                        type=BlockType.CODE,
                        label=fname,
                        content=data.decode("utf-8", "replace"),
                        meta={"language": "python", "filename": fname}
                    ))
                
                # B. Structured Data (JSON/CSV) - Potentially Visual
                elif lower_fname.endswith(".json"):
                    try:
                        json_content = json.loads(data)
                        visual_blocks.append(ContentBlock(
                            type=BlockType.DATA,
                            label=fname,
                            content=json_content,
                            meta={"filename": fname, "mime_type": "application/json"}
                        ))
                    except:
                        pass # Fallback to FILE block only

                # C. Text Analysis Reports / Markdown (Lower Priority)
                # These caused the issue by appearing at the top. Now they go to report_blocks.
                elif lower_fname.endswith((".txt", ".md", ".log")):
                    report_blocks.append(ContentBlock(
                        type=BlockType.MARKDOWN,
                        label=fname,
                        content=data.decode("utf-8", "replace"),
                        meta={"filename": fname}
                    ))

                # Always append FILE block for Asset Management (Physical persistence)
                # These are usually rendered as a download list at the bottom.
                asset_blocks.append(self._create_file_block(fname, data, fhash))
            else:
                asset_blocks.append(ContentBlock(
                    type=BlockType.FILE,
                    label=fname,
                    meta={"filename": fname, "blob_hash": fhash}
                ))

        # 6. Inject Console Logs (High Priority)
        # Console should typically appear right after Code or at the bottom of the "Main" section.
        console_block = ContentBlock(
            type=BlockType.MARKDOWN,
            label="Execution Log",
            content="\n".join(logs[-2000:]),
            render_type=RenderType.LOG_CONSOLE,
            tags=[SystemTags.EXECUTION_LOGS]
        )

        # 7. Assemble Final Block List in Strict Visual Order
        # Layout Logic:
        # 1. Code (The Source)
        # 2. Console (The Execution)
        # 3. Visuals (The Result Data)
        # 4. Reports (The Analysis Text)
        # 5. Assets (The Downloads)
        blocks = code_blocks + [console_block] + visual_blocks + report_blocks + asset_blocks
        
        # [FIX END]

        output = NodeOutput(
            # Populate thought with summary (optional, or rely on console log)
            thought="Agentic execution completed.",
            blocks=blocks, 
            metadata={"mode": "agentic", "exit_code": exit_code}
        )
        self._ensure_ids(output)
        saved = await self.assets.process_and_save(output)
        self._enrich_metadata(saved, start_time, mode="agentic")
        return [saved]

    async def _run_interactive_mode(
        self,
        project_id: str,
        user_input: Dict[str, Any],
        manifest: Dict[str, str],
        previous_output: Optional[NodeOutput],
        start_time: datetime,
        asset_map: Optional[Dict[str, str]] = None,
        runtime: Optional[RuntimeConfig] = None  # [BYOK]
    ) -> List[NodeOutput]:
        # 1. Attempt to reuse active session
        e2b_key = runtime.e2b_api_key if (runtime and runtime.e2b_api_key) else settings.E2B_API_KEY
        sb = await self.sandbox.get_active_session(project_id, api_key=e2b_key)

        if not sb:
            logger.info(f"Interactive Mode: Session expired for {project_id}, hydrating new one...")
            sb = await self.sandbox.start_agentic_session(
                project_id,
                "interactive-restore",
                runtime=runtime,  # [BYOK]
                context_manifest=manifest if not asset_map else None,
                layout=manifest if asset_map else None
            )

        # 2. Extract User Code
        inputs = user_input.get("inputs", {}) if user_input else {}
        code = user_input.get("manual_content") or inputs.get("manual_content")
        if not code and previous_output:
            blk = previous_output.get_block("code")
            if blk:
                code = blk.content

        if not code:
            raise ExecutionError("Input", "No code provided")

        # 3. Native Execution (Hot Swap)
        wd = settings.SANDBOX_DATA_DIR
        await sb.files.write(f"{wd}/script.py", code)

        # [BYOK] Resolve LLM keys for user code execution
        llm_key = (runtime.llm_api_key if runtime else None) or settings.OPENAI_API_KEY or settings.API_KEY
        native_env = {
            "TAVILY_API_KEY": settings.TAVILY_API_KEY,
            "OPENAI_API_KEY": llm_key or "",
            "MPLBACKEND": "Agg",
            "PYTHONPATH": "/home/user/.local/lib/python3.11/site-packages:$PYTHONPATH",
            "NO_COLOR": "true"
        }
        proc = await sb.commands.run(
            "python3 script.py",
            cwd=wd,
            envs=native_env,
            timeout=settings.SANDBOX_EXECUTION_TIMEOUT
        )

        log_parts = []
        if proc.stdout:
            log_parts.append(f"[STDOUT]\n{proc.stdout}")
        if proc.stderr:
            log_parts.append(f"[STDERR]\n{proc.stderr}")
        raw_logs = "\n".join(log_parts) if log_parts else "[SYSTEM]\n(No output produced)"
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_logs = ansi_escape.sub("", raw_logs)

        # 4. Harvest Diff (Sync new plots/files)
        normalized_manifest = self._normalize_manifest_paths(manifest)
        new_files, full_state_map = await self.sandbox.harvest_artifacts_diff(sb, normalized_manifest)

        # 5. Package
        blocks: List[ContentBlock] = [
            ContentBlock(
                type=BlockType.CODE,
                label="script.py",
                content=code,
                meta={"language": "python", "edited": True}
            ),
            ContentBlock(
                type=BlockType.MARKDOWN,
                label="Console",
                content=clean_logs,
                render_type=RenderType.LOG_CONSOLE,
                tags=[SystemTags.EXECUTION_LOGS]
            )
        ]

        for fname, fhash in full_state_map.items():
            if fname in new_files:
                data = new_files[fname]
                blocks.append(self._create_file_block(fname, data, fhash))
            else:
                blocks.append(ContentBlock(
                    type=BlockType.FILE,
                    label=fname,
                    meta={"filename": fname, "blob_hash": fhash}
                ))

        output = NodeOutput(blocks=blocks, metadata={"mode": "interactive", "exit_code": proc.exit_code})
        self._ensure_ids(output)
        saved = await self.assets.process_and_save(output)
        self._enrich_metadata(saved, start_time, mode="interactive")
        return [saved]

    def _enrich_metadata(self, output: NodeOutput, start_time: datetime, mode: str = "gen"):
        duration = (datetime.utcnow() - start_time).total_seconds()
        output.metadata.update({
            "execution_duration": duration,
            "timestamp": start_time.isoformat(),
            "mode": mode
        })

    def _normalize_manifest_paths(self, manifest: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize virtual paths to sandbox-relative paths (align with tarball arcname logic).
        """
        normalized: Dict[str, str] = {}
        for v_path, blob_hash in (manifest or {}).items():
            parts = Path(v_path).parts
            if len(parts) > 2 and parts[0] == "history":
                rel = str(Path(*parts[2:]))
            else:
                rel = v_path.lstrip("/")
            if rel:
                normalized[rel] = blob_hash
        return normalized

    def _truncate_log(self, log: str, max_lines: int = 1000) -> str:
        """
        Smart truncation for error logs.
        Keeps Head (Error Type) and Tail (Traceback/Recent Calls).
        """
        lines = log.splitlines()
        if len(lines) <= max_lines:
            return log
        
        head = 500
        tail = 500
        
        truncated = lines[:head] + [f"\n... [Skipped {len(lines) - head - tail} lines of logs] ...\n"] + lines[-tail:]
        return "\n".join(truncated)

    def _post_process_outline(self, output: NodeOutput):
        """
        Normalizes outline output to ensure a List[str] is available
        under a DATA block labeled "outline".
        """
        blk = output.get_block("outline") or output.get_block("json")
        if not blk:
            return

        outline = None
        if isinstance(blk.content, dict):
            outline = blk.content.get("outline")
        elif isinstance(blk.content, list):
            outline = blk.content
        elif isinstance(blk.content, str):
            lines = [ln.strip(" 	-*") for ln in blk.content.splitlines() if ln.strip()]
            outline = lines if lines else None

        if outline is None:
            return

        normalized = [str(x).strip() for x in outline if str(x).strip()]
        if not normalized:
            return

        # [FIX] Do not flatten to list. Preserve dictionary wrapper for Frontend SCA contract.
        # SCA Option Card expects: { "outline": [...] } to identify it as an Outline list.
        if blk.label.lower() == "outline":
            if isinstance(blk.content, dict):
                blk.content["outline"] = normalized
            else:
                # If the original block was raw list or string, re-wrap it properly
                blk.content = {"outline": normalized, "__kind__": "outline"}
        else:
            # If we found it in a generic JSON block, append a specific outline block
            # This path likely creates a new block, so we should ensure it's also a dict
            output.blocks.append(ContentBlock(
                type=BlockType.DATA,
                label="outline",
                # [FIX] Ensure appended block is also wrapped
                content={"outline": normalized, "__kind__": "outline"}, 
                tags=["system_generated"]
            ))

    def _coerce_outline(self, value) -> List[Union[str, Dict[str, Any]]]:
        if isinstance(value, dict):
            if "paper_plan" in value:
                value = value.get("paper_plan")
            elif "outline" in value:
                value = value.get("outline")
            elif "structure" in value:
                value = value.get("structure")
            else:
                value = value.get("items") or value.get("data")

        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                return value
            return [str(x).strip() for x in value if str(x).strip()]

        if isinstance(value, str):
            lines = [ln.strip(" \t-*") for ln in value.splitlines() if ln.strip()]
            return lines

        return []

    def _wrap_paper_output(self, ws: PaperWorkspace) -> NodeOutput:
        blocks = []

        if ws.files.get("main.pdf"):
            pdf = ws.files["main.pdf"]
            if pdf.blob_hash:
                pdf_block = pdf.to_content_block()
                pdf_block.label = "Paper.pdf"
                pdf_block.meta["filename"] = "main.pdf"
                blocks.append(pdf_block)

        file_tree = {}
        for path, vf in ws.files.items():
            entry = {
                "type": vf.file_type.value,
                "readonly": vf.is_readonly,
            }
            if vf.content is not None:
                entry["content"] = vf.content
            if vf.blob_hash:
                entry["blob_hash"] = vf.blob_hash
            file_tree[path] = entry

        blocks.append(ContentBlock(
            type=BlockType.DATA,
            label="Workspace",
            content=file_tree,
            render_type=RenderType.IDE_WORKSPACE,
            tags=["workspace_state"],
            meta={"full_state": ws.model_dump(mode="json")},
        ))

        log_tags = [SystemTags.EXECUTION_LOGS]
        if ws.compile_status == CompileStatus.ERROR:
            log_tags.append(SystemTags.PRIMARY_ERROR)
        log_content = ws.last_build_log or ""
        if log_content and "[STDOUT]" not in log_content and "[STDERR]" not in log_content:
            tag = "[STDERR]" if ws.compile_status == CompileStatus.ERROR else "[STDOUT]"
            log_content = f"{tag}\n{log_content}"
        blocks.append(ContentBlock(
            type=BlockType.MARKDOWN,
            label="Build Log",
            content=log_content,
            render_type=RenderType.LOG_CONSOLE,
            tags=log_tags,
        ))

        exit_code = 0 if ws.compile_status == CompileStatus.SUCCESS else 1
        return NodeOutput(blocks=blocks, metadata={"exit_code": exit_code})

    def _ensure_ids(self, output: NodeOutput):
        """
        [CRITICAL FIX] Recursively ensures all blocks have a UUID.
        Standard Output Parser usually assigns one via Pydantic default,
        but explicit check handles manually constructed blocks.
        """
        queue = list(output.blocks)
        while queue:
            block = queue.pop(0)
            if not block.id:
                block.id = str(uuid4())
            if block.children:
                queue.extend(block.children)

    def _reconcile_identities(self, new_outputs: List[NodeOutput], previous_output: Optional[NodeOutput]):
        """
        [Identity Persistence Algorithm]
        Matches new blocks with previous blocks by (Type, Label) to reuse IDs.
        Prevents React component unmounting and focus loss in frontend.
        """
        if not previous_output or not new_outputs:
            return

        # 1. Build Index of Previous Blocks
        # Map: (Type, Label) -> List[ID] (Queue to handle duplicates)
        id_map: Dict[tuple, List[str]] = {}
        
        def index_blocks(blocks):
            for b in blocks:
                key = (b.type, b.label)
                if key not in id_map:
                    id_map[key] = []
                id_map[key].append(b.id)
                if b.children:
                    index_blocks(b.children)
        
        index_blocks(previous_output.blocks)

        # 2. Assign IDs to New Blocks
        def assign_ids(blocks):
            for b in blocks:
                key = (b.type, b.label)
                if key in id_map and id_map[key]:
                    # Reuse existing ID (FIFO)
                    b.id = id_map[key].pop(0)
                # Else: keep the newly generated UUID
                
                if b.children:
                    assign_ids(b.children)

        # Only reuse IDs if we are in a linear update path (single output)
        # For SCA (multiple outputs), reusing IDs across options is dangerous 
        # unless we explicitly track option lineage.
        if len(new_outputs) == 1:
            assign_ids(new_outputs[0].blocks)

    async def _publish_progress(self, project_id: str, node_id: str, event_type: str, data: Dict[str, Any]):
        """
        [NEW] 发布进度事件到前端
        """
        if not self.bus:
            return
        try:
            await self.bus.publish(
                f"project:{project_id}",
                event_type,
                {"node_id": node_id, **data}
            )
        except Exception as e:
            logger.warning(f"Failed to publish progress event: {e}")
