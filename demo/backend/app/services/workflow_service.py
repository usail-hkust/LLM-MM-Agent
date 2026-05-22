"""
Workflow Service - The Orchestrator.

Manages the lifecycle of the project. 
[REFACTORED] Implements Strict Linear Pipeline with Auto-Cascading.
[OPTIMIZED] Non-Destructive Linear Execution: No downstream invalidation, no auto-re-run of existing nodes.
[FIXED] Implemented Vectorized Patch Protocol for Atomic Multi-Block Updates.
[FIXED] The State Black Hole in Callbacks: Ensure state recovery on task cancellation/failure.
"""
import asyncio
import logging
import json
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy import update
from redis.asyncio import Redis
from app.core.events import EventBus
from app.core.definitions import NodeStatus, BlockType, NodeType, VersionTrigger
from app.core.exceptions import StateError, ResourceNotFoundError
from app.core.config import settings

from app.domain.models import Project, NodeVersion, NodeState
from app.domain.registry import registry
from app.domain.payloads import RunNodeCommand, UpdateNodeCommand, CommitNodeCommand
from app.domain.events import NodeStatusEvent, NodeUpdateEvent, TimelineUpdateEvent, ErrorEvent

from app.infra.persistence.repositories import ProjectRepository, VersionRepository
from app.infra.persistence.database import AsyncSessionLocal # [FIX] Import session factory
from app.infra.persistence.models import NodeStateDB
from app.services.node_processor import NodeProcessor
from app.services.context_service import ContextService
from app.services.topology_service import TopologyService
from app.services.input_resolver import InputResolver
from app.services.ingestion_service import IngestionService
from app.api.schemas import InteractionRequest, RuntimeConfig

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    [The Writer / State Machine]
    Manages Project State transitions and orchestrates async execution.
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        version_repo: VersionRepository,
        processor: NodeProcessor,
        context_service: ContextService,
        topology_service: TopologyService,
        input_resolver: InputResolver,
        event_bus: EventBus,
        ingestion_service: IngestionService,
        redis_client: Optional[Redis] = None
    ):
        self.p_repo = project_repo
        self.v_repo = version_repo
        self.processor = processor
        self.ctx_service = context_service
        self.topo_service = topology_service
        self.resolver = input_resolver
        self.bus = event_bus
        self.ingestion = ingestion_service
        self.redis_client = redis_client

    # --- Redis Helper Methods ---
    
    def _get_node_lock_key(self, project_id: str, node_id: str) -> str:
        """Get Redis lock key for node execution."""
        return f"{settings.REDIS_PREFIX}:lock:node:{project_id}:{node_id}"
    
    def _get_draft_key(self, project_id: str, node_id: str) -> str:
        """Get Redis Hash key for draft content (Write-Behind)."""
        return f"{settings.REDIS_PREFIX}:draft:{project_id}:{node_id}"
    
    async def _flush_draft_to_db(self, project_id: str, node_id: str) -> bool:
        """
        Flush draft content from Redis Hash to database.
        Returns True if flush occurred, False if no dirty data.
        """
        if not self.redis_client:
            return False
        
        try:
            draft_key = self._get_draft_key(project_id, node_id)
            # Get all fields from Redis Hash
            draft_data = await self.redis_client.hgetall(draft_key)
            
            if not draft_data:
                return False
            
            # Parse edits map from Redis
            edits = {}
            for block_id, content_json in draft_data.items():
                try:
                    edits[block_id] = json.loads(content_json)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse draft content for block {block_id}")
                    continue
            
            if not edits:
                return False
            
            # Apply batch update (force flush to DB, bypassing Write-Behind)
            await self.batch_update_draft_content(project_id, node_id, edits, force_flush=True)
            
            # Clear Redis Hash after successful flush
            await self.redis_client.delete(draft_key)
            
            logger.info(f"Flushed draft content for node {node_id} to DB ({len(edits)} blocks)")
            return True
        except Exception as e:
            logger.error(f"Failed to flush draft to DB: {e}", exc_info=True)
            return False

    async def sanitize_stuck_nodes(self):
        """
        [NEW] Startup Hook.
        Resets nodes stuck in DRAFTING/RUNNING (due to server crash) to FAILED.
        """
        logger.info("Running Zombie Node Sanitation...")
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Find all nodes currently in DRAFTING state (which implies running/processing)
                # and force them to FAILED so they can be re-run manually.
                stmt = (
                    update(NodeStateDB)
                    .where(NodeStateDB.status == NodeStatus.DRAFTING)
                    .values(
                        status=NodeStatus.FAILED,
                        updated_at=datetime.utcnow()
                    )
                )
                result = await session.execute(stmt)
                
                if result.rowcount > 0:
                    logger.warning(f"Sanitized {result.rowcount} zombie nodes (DRAFTING -> FAILED).")
                else:
                    logger.info("No zombie nodes found.")

    # --- Public Commands ---

    # --- Interaction Dispatcher (The new entry point) ---

    async def handle_interaction(self, project_id: str, request: InteractionRequest, runtime: Optional[RuntimeConfig] = None) -> None:
        """
        Dispatches generic UI actions.
        [FIX] Implemented Vectorized Patch Protocol (Save-before-Run).
        Accepts 'new_content' dict for multi-block atomic updates.
        """
        logger.info(f"Handling interaction: {request.action} on {request.node_id}")
        
        payload = request.payload
        
        try:
            # === [VECTORIZED PRE-SAVE] ===
            # Detect and apply all edits carried in the payload BEFORE performing logic.
            # This fixes the "IDE Split View" issue where only the focused block was saved.
            edits_map = {}
            
            # 1. Extract Vector State (Primary Source)
            # Frontend StageFormWrapper sends 'new_content': { block_id: value }
            if "new_content" in payload and isinstance(payload["new_content"], dict):
                edits_map.update(payload["new_content"])
            
            # 2. Extract Scalar State (Legacy/Fallback Source)
            # AtomShell injects 'manual_content' + 'block_id' for specific actions
            if "manual_content" in payload and "block_id" in payload:
                # Merge into map (Last Writer Wins if collision, though unlikely)
                edits_map[payload["block_id"]] = payload["manual_content"]

            # 3. Perform Atomic Batch Update
            # Only hit the DB if we actually have edits
            if edits_map:
                logger.info(f"Interaction carries {len(edits_map)} edits. Performing atomic save.")
                # We MUST await this to ensure persistence before execution logic reads from DB
                await self.batch_update_draft_content(
                    project_id,
                    request.node_id,
                    edits_map
                )
            # =============================

            if request.action == "run_node":
                inputs = payload.get("inputs", {})
                cmd = RunNodeCommand(
                    project_id=project_id,
                    node_id=request.node_id,
                    instruction=payload.get("instruction"),
                    inputs=inputs,
                    intent=payload.get("intent", "generate"),
                    config=payload.get("config", {})
                )
                await self.run_node(cmd, runtime=runtime)

            elif request.action == "save_draft":
                # Logic handled by Vectorized Pre-Save above.
                # Just logging acknowledgment.
                logger.debug("Explicit save_draft processed via batch update.")

            elif request.action == "select_option":
                # Convergence: Create new version with ONLY the selected option
                await self.select_and_converge(
                    project_id, 
                    request.node_id, 
                    payload.get("option_index")
                )
            
            # [FIX] New Atomic Action: Select + Commit + Cascade
            elif request.action == "select_and_commit":
                # Edits (updated_content) handled by Vectorized Pre-Save above.
                
                # 2. Select (Converge to new version)
                await self.select_and_converge(
                    project_id, 
                    request.node_id, 
                    payload.get("option_index")
                )
                
                # 3. Commit
                cmd = CommitNodeCommand(project_id=project_id, node_id=request.node_id)
                await self.commit_node(cmd, runtime=runtime)

            elif request.action == "approve_node":
                cmd = CommitNodeCommand(project_id=project_id, node_id=request.node_id)
                await self.commit_node(cmd, runtime=runtime)

            elif request.action == "reject_node":
                # Refinement: Creates a NEW version via the 'refine' intent
                feedback = payload.get("feedback", "Rejected")
                
                # [FIX] Preserve Original Instruction
                # We must fetch the PREVIOUS instruction so the LLM knows WHAT to refine.
                # Otherwise, it just sees "Refinement based on feedback: ..." and loses the actual task.
                new_instruction = f"**Strategic Iteration based on Peer Review**: {feedback}"
                
                try:
                    # 1. Fetch Node State to find working/stable version
                    # We can't reuse a session easily here without refactoring, so we use repo helpers
                    pid = UUID(project_id)
                    project = await self.p_repo.get(pid)
                    if project:
                        node_state = project.nodes.get(request.node_id)
                        if node_state:
                            # Try working then stable
                            target_ver_id = node_state.working_version_id or node_state.stable_version_id
                            if target_ver_id:
                                ver = await self.v_repo.get(target_ver_id)
                                if ver and ver.provenance:
                                    # Extract original instruction from snapshot
                                    snapshot = ver.provenance.get("inputs_snapshot", {})
                                    original_instr = snapshot.get("instruction")
                                    if original_instr:
                                        # Append Feedback to Original
                                        new_instruction = f"{original_instr}\n\n**Strategic Iteration based on Peer Review**: {feedback}"
                                        logger.info(f"Refinement: Preserved original instruction length {len(original_instr)}")
                except Exception as e:
                    logger.warning(f"Failed to recover original instruction for refinement: {e}")

                cmd = RunNodeCommand(
                    project_id=project_id,
                    node_id=request.node_id,
                    instruction=new_instruction,
                    inputs={"feedback": feedback},
                    intent="refine",
                    config={"num_samples": 1} 
                )
                await self.run_node(cmd, runtime=runtime)

            # [FIX ISSUE 5] Handle Reset Action
            # Prevents frontend crash by ensuring the action actually does something (resets state)
            elif request.action == "reset":
                await self.reset_node(project_id, request.node_id)
                # [FIX ISSUE 1] Support "Reset & Run" atomic behavior
                if payload.get("run_after_reset"):
                    logger.info(f"Auto-running node {request.node_id} after reset.")
                    cmd = RunNodeCommand(
                        project_id=project_id,
                        node_id=request.node_id,
                        intent="generate",
                        inputs={"auto_triggered": True}
                    )
                    # Dispatch background run to avoid blocking the response
                    self._dispatch_background_task(
                        self.run_node(cmd, runtime=runtime),
                        project_id=project_id,
                        node_id=request.node_id
                    )

            # ... fork/restore generic handling logic (remains similar, just using payload) ...
            elif request.action == "fork_node":
                # [FIX] Issue 2: Parameter Resolution (Index -> ID)
                base_vid = None
                try:
                    if "base_version_id" in payload:
                        base_vid = UUID(payload["base_version_id"])
                    elif "base_version_index" in payload:
                        idx = int(payload["base_version_index"])
                        base_vid = await self._resolve_version_by_index(project_id, request.node_id, idx)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid version identifier format: {e}")
                
                if not base_vid:
                    raise ValueError("fork_node requires valid base_version_id or base_version_index")

                await self.fork_node(
                    project_id=project_id,
                    node_id=request.node_id,
                    base_version_id=base_vid,
                    target_output_index=payload.get("target_output_index")
                )
                
            elif request.action == "restore_node":
                # [FIX] Issue 2: Parameter Resolution (Index -> ID)
                target_vid = None
                try:
                    if "version_id" in payload:
                        target_vid = UUID(payload["version_id"])
                    elif "version_index" in payload:
                        idx = int(payload["version_index"])
                        target_vid = await self._resolve_version_by_index(project_id, request.node_id, idx)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid version identifier format: {e}")
                
                if not target_vid:
                    raise ValueError("restore_node requires valid version_id or version_index")

                await self.restore_node(
                    project_id=project_id,
                    node_id=request.node_id,
                    version_id=target_vid
                )
            
        except Exception as e:
            logger.error(f"Interaction failed: {e}", exc_info=True)
            raise e

    async def _resolve_version_by_index(self, project_id: str, node_id: str, index: int) -> Optional[UUID]:
        """
        [FIX] Helper to map integer index (from Timeline UI) to Version UUID.
        Assumes Index 0 = First Created Version (Oldest).
        """
        pid = UUID(project_id)
        # Fetch summaries (sorted descending by default in repo)
        summaries = await self.v_repo.list_summaries_by_node(pid, node_id)
        
        # Sort ASC to match logical index (0=First)
        # Summaries contain { "id", "created_at", ... }
        summaries.sort(key=lambda x: x["created_at"])
        
        if 0 <= index < len(summaries):
            return summaries[index]["id"]
        
        logger.warning(f"Version index {index} out of bounds for node {node_id} (count: {len(summaries)})")
        return None

    async def _resolve_output_index_by_artifact(self, version_id: UUID, artifact_id: str) -> Optional[int]:
        """
        [FIX] Helper to find which output index contains a specific artifact ID.
        """
        version = await self.v_repo.get(version_id)
        if not version or not version.outputs:
            return None
            
        for idx, output in enumerate(version.outputs):
            # Check deep blocks
            found = self._find_block_by_id(output.blocks, artifact_id)
            if found:
                return idx
        return None

    # --- Core Logic Implementation ---

    async def create_project(
        self, 
        name: str, 
        owner_id: str, 
        assets: Dict[str, str] = None, 
        initial_instruction: str = None,
        runtime: Optional[RuntimeConfig] = None
    ) -> Project:
        """
        Initializes a new project and AUTO-STARTS the first node.
        """
        project_id = uuid4()
        assets = assets or {}
        
        nodes = {}
        first_node_id = None
        
        sorted_blueprints = sorted(registry.get_all(), key=lambda b: registry.get_global_index(b.id))
        if sorted_blueprints:
            first_bp = sorted_blueprints[0]
            first_node_id = first_bp.id
            
            # [FIX] Force DRAFTING status immediately for the first node
            nodes[first_node_id] = NodeState(
                node_id=first_node_id,
                base_id=first_node_id,
                iteration_index=None,
                status=NodeStatus.DRAFTING 
            )
            
        project = Project(
            id=project_id,
            name=name,
            owner_id=owner_id,
            nodes=nodes,
            assets=assets
        )
        
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self.p_repo.save(project, session=session)
        
        # [FIX] Always Auto-Start the workflow
        # Ensure we have a default instruction if none provided
        safe_instruction = initial_instruction or "Initialize the strategic modeling framework and assess the landscape of available data assets."
        
        if first_node_id:
            logger.info(f"🚀 Auto-starting workflow for Project {project_id} via Node {first_node_id}")
            cmd = RunNodeCommand(
                project_id=str(project_id),
                node_id=first_node_id,
                instruction=safe_instruction,
                inputs={
                    "file_manifest": assets,
                    "auto_started": True
                },
                intent="generate"
            )
            # Notify UI immediately that it's running
            await self._emit(str(project_id), NodeStatusEvent(first_node_id, NodeStatus.DRAFTING))
            self._dispatch_background_task(
                self.run_node(cmd, runtime=runtime),
                project_id=str(project_id),
                node_id=first_node_id
            )

        return project

    async def update_project(self, project_id: str, name: Optional[str] = None, assets: Optional[Dict[str, str]] = None) -> Project:
        """Updates project metadata."""
        pid = UUID(project_id)
        project = await self._get_project_or_fail(pid)
        
        if name:
            project.name = name
        if assets:
            project.assets.update(assets)
            
        await self.p_repo.save(project)
        return project

    async def delete_project(self, project_id: str) -> None:
        """Deletes a project."""
        pid = UUID(project_id)
        success = await self.p_repo.delete(pid)
        if not success:
            raise ResourceNotFoundError("Project", project_id)

    async def run_node(self, cmd: RunNodeCommand, runtime: Optional[RuntimeConfig] = None) -> None:
        """
        [Execution Handler]
        Triggers execution. 
        [FIX] Handles Lazy Initialization of missing nodes gracefully.
        [REFACTORED] Smart Ingestion: Skips text extraction for Agentic nodes.
        [ENHANCED] Distributed Lock: Prevents duplicate execution across instances.
        [ENHANCED] Draft Write-Behind: Flushes pending edits before execution.
        Flow: DRAFTING -> [Async Process] -> REVIEWING (Stop).
        """
        # Flush any pending draft edits before execution
        await self._flush_draft_to_db(cmd.project_id, cmd.node_id)
        
        # Distributed lock to prevent duplicate execution
        lock_key = self._get_node_lock_key(cmd.project_id, cmd.node_id)
        lock_acquired = False
        
        if self.redis_client:
            try:
                # Try to acquire lock (non-blocking, 5 second timeout)
                lock_acquired = await self.redis_client.set(
                    lock_key,
                    "locked",
                    nx=True,  # Only set if not exists
                    ex=5  # 5 second expiration
                )
                if not lock_acquired:
                    logger.warning(f"Node {cmd.node_id} is already running (lock held by another instance)")
                    return
            except Exception as e:
                logger.warning(f"Failed to acquire distributed lock: {e}, proceeding anyway")
        
        try:
            pid = UUID(cmd.project_id)
            effective_id = cmd.node_id

            # [REFACTOR] Resolve Blueprint early to check capabilities
            base_id = effective_id.split('-')[0] if '-' in effective_id else effective_id
            blueprint = registry.get(base_id)
            
            # Check if this is an Agentic Node
            is_agentic = blueprint and blueprint.meta.get("executor_engine") == "agentic_claude"

            # Asset Hydration (if uploaded via CLI/Input)
            if "file_manifest" in cmd.inputs and cmd.inputs["file_manifest"]:
                 # Always register assets to CAS
                 await self._hydrate_assets(pid, cmd.inputs["file_manifest"])
                 
                 if not is_agentic:
                     # [PATH A] Standard Node (e.g., 1.1 Generator): Needs text ingestion
                     # Extract text from PDFs/Docs to feed the LLM context
                     cmd.instruction, cmd.inputs["dataset_files"] = await self.ingestion.process_inputs(
                        cmd.inputs["file_manifest"], cmd.instruction or "", runtime=runtime
                    )
                 else:
                     # [PATH B] Agentic Node (e.g., 1.2 Executor): Skip text ingestion
                     # Agent explores files autonomously via 'ls', 'cat', etc.
                     # Just pass the list of filenames so the prompt knows what's available
                     cmd.inputs["dataset_files"] = list(cmd.inputs["file_manifest"].keys())
                     logger.info(f"Skipping Context Ingestion for Agentic Node {effective_id}")

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    project = await self.p_repo.get(pid, session=session)
                    if not project: 
                        raise ResourceNotFoundError("Project", str(pid))
                    
                    # [CRITICAL FIX] Use Domain Helper get_node()
                    # This creates the NodeState object in memory if it doesn't exist (Lazy Init)
                    node_state = project.get_node(effective_id)
                    
                    # [CRITICAL FIX] Persist the potentially new node immediately
                    # If status was VOID, we are starting it now.
                    if node_state.status == NodeStatus.VOID or node_state.status == NodeStatus.LOCKED:
                        node_state.status = NodeStatus.DRAFTING
                        node_state.updated_at = datetime.utcnow()
                        await self.p_repo.update_node_state(str(pid), node_state, session=session)
                    
                    # Lock Check (Skip if Auto-Triggered or already DRAFTING)
                    is_auto = cmd.inputs.get("auto_triggered", False) or cmd.inputs.get("auto_started", False)
                    if not is_auto and node_state.status != NodeStatus.DRAFTING:
                        if not self.topo_service.is_node_runnable(project, effective_id) and node_state.status != NodeStatus.FAILED:
                            raise StateError(f"Node {effective_id} is locked or not ready.")

                    # Determine Trigger Logic
                    trigger = VersionTrigger.INITIAL_RUN
                    if cmd.intent == "refine": 
                        trigger = VersionTrigger.REFINE
                    elif cmd.intent == "execute_only": 
                        trigger = VersionTrigger.EDIT

                    parent_version_id = node_state.working_version_id or node_state.stable_version_id
                    
                    # Blueprint already resolved above for ingestion routing

            await self._emit(cmd.project_id, NodeStatusEvent(effective_id, NodeStatus.DRAFTING))

            # Dispatch Worker
            self._dispatch_background_task(
                self._bg_run_task(cmd.project_id, effective_id, blueprint, cmd, cmd.intent, cmd.config, trigger, parent_version_id, runtime),
                project_id=cmd.project_id,
                node_id=effective_id
            )
        finally:
            # Release lock after successful dispatch or on error
            if lock_acquired and self.redis_client:
                try:
                    await self.redis_client.delete(lock_key)
                except Exception as e:
                    logger.warning(f"Failed to release lock: {e}")

    async def update_node(self, cmd: UpdateNodeCommand) -> None:
        """
        Transition: Modify Working Version (Manual Edit / Selection).
        Does NOT trigger re-execution.
        """
        pid = UUID(cmd.project_id)
        nid = cmd.node_id
        
        project = await self._get_project_or_fail(pid)
        node_state = project.nodes.get(nid)
        
        if not node_state or not node_state.working_version_id:
            raise StateError("No active working draft to update.")

        # Load Heavy Version
        version = await self.v_repo.get(node_state.working_version_id)
        if not version:
            raise ResourceNotFoundError("NodeVersion", str(node_state.working_version_id))

        # Mutate (In-Place Update of the Record)
        # Note: In a stricter immutable system, we would clone. 
        # Here we allow mutation of the 'Draft' phase for UX responsiveness.
        
        changed = False
        
        # 1. Handle Selection
        if cmd.selected_output_id:
            # Deselect all, select target
            # Note: Since NodeOutput doesn't have a top-level ID, we use the output index
            # In production, you might want to add an ID field to NodeOutput or use a different mechanism
            if version.outputs:
                try:
                    # Try to parse as index
                    output_idx = int(cmd.selected_output_id)
                    if 0 <= output_idx < len(version.outputs):
                        for i, out in enumerate(version.outputs):
                            out.is_selected = (i == output_idx)
                        changed = True
                    else:
                        logger.warning(f"Invalid output index {output_idx} for node {nid}")
                except ValueError:
                    # If not an index, just select the last output (fallback)
                    logger.warning(f"selected_output_id is not a valid index: {cmd.selected_output_id}, selecting last output")
                    for out in version.outputs:
                        out.is_selected = False
                    if version.outputs:
                        version.outputs[-1].is_selected = True
                        changed = True

        # 2. Handle Manual Content Edit (VARL/Refine Prep)
        if cmd.manual_content and cmd.target_block_id:
            # Deep search and update
            for output in version.outputs:
                block = self._find_block_by_id(output.blocks, cmd.target_block_id)
                if block:
                    block.content = cmd.manual_content
                    if "edited" not in block.tags:
                        block.tags.append("edited")
                    # Auto-select the edited output if multiple exist
                    if len(version.outputs) > 1:
                        for out in version.outputs:
                            out.is_selected = False
                        output.is_selected = True
                    changed = True
                    break

        if changed:
            # Pragmatic immutability: Update draft in-place for manual edits during REVIEWING phase
            await self.v_repo.update_draft(version)
            # Notify frontend with updated data
            version_dump = version.model_dump(mode='json')
            await self._emit(cmd.project_id, NodeUpdateEvent(nid, version_dump))

    async def commit_node(self, cmd: CommitNodeCommand, runtime: Optional[RuntimeConfig] = None) -> None:
        """
        [The Atomic Trigger]
        1. Mandatory HITL Check: Node must be REVIEWING.
        2. Commit: Lock current node status.
        3. Expand: If Driver, generate downstream placeholders.
        4. Cascade: Auto-Run next node.
        [ENHANCED] Distributed Lock: Ensures atomic commit across instances.
        [ENHANCED] Draft Write-Behind: Flushes pending edits before commit.
        """
        # Flush any pending draft edits before commit
        await self._flush_draft_to_db(cmd.project_id, cmd.node_id)
        
        # Distributed lock to ensure atomic commit
        lock_key = self._get_node_lock_key(cmd.project_id, cmd.node_id)
        lock_acquired = False
        
        if self.redis_client:
            try:
                # Try to acquire lock (non-blocking, 10 second timeout)
                lock_acquired = await self.redis_client.set(
                    lock_key,
                    "locked",
                    nx=True,  # Only set if not exists
                    ex=10  # 10 second expiration
                )
                if not lock_acquired:
                    logger.warning(f"Node {cmd.node_id} commit is already in progress (lock held by another instance)")
                    raise StateError(f"Node {cmd.node_id} commit is already in progress")
            except StateError:
                raise
            except Exception as e:
                logger.warning(f"Failed to acquire distributed lock: {e}, proceeding anyway")
        
        try:
            pid = UUID(cmd.project_id)
            nid = cmd.node_id

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    project = await self.p_repo.get(pid, session=session)
                    if not project: 
                        raise ResourceNotFoundError("Project", str(pid))
                    
                    node_state = project.nodes.get(nid)
                    if not node_state: 
                        raise ResourceNotFoundError("Node", nid)

                    # 1. Mandatory HITL Check
                    if node_state.status != NodeStatus.REVIEWING:
                        raise StateError(f"Node {nid} is in {node_state.status}. Must be REVIEWING to approve.")

                    # 2. Lock Down
                    node_state.status = NodeStatus.COMMITTED
                    node_state.stable_version_id = node_state.working_version_id
                    node_state.updated_at = datetime.utcnow()

                    # 3. Eager Expansion
                    if registry.is_driver(node_state.base_id):
                        version = await self.v_repo.get(node_state.stable_version_id, session=session)
                        if version and version.selected_output:
                            items = self._extract_list_from_output(version.selected_output)
                            if items:
                                await self.topo_service.expand_topology(project, nid, len(items), session=session)

                    # Persist changes BEFORE cascading (so next task sees committed state)
                    await self.p_repo.update_node_state(str(pid), node_state, session=session)
                    await self.p_repo.save(project, session=session)

            # Notify
            await self._emit(str(pid), NodeStatusEvent(nid, NodeStatus.COMMITTED))
            await self._emit(str(pid), TimelineUpdateEvent(str(pid)))
            
            # 4. Auto-Cascade (The Solution)
            await self._cascade_to_next_node(pid, nid, runtime=runtime)
        finally:
            # Release lock after successful commit or on error
            if lock_acquired and self.redis_client:
                try:
                    await self.redis_client.delete(lock_key)
                except Exception as e:
                    logger.warning(f"Failed to release lock: {e}")

    # --- Branching & History Management ---

    async def fork_node(
        self, 
        project_id: str, 
        node_id: str, 
        base_version_id: UUID, 
        target_output_index: Optional[int] = None
    ) -> None:
        """
        Creates a new WORKING draft (Branch) from a historical point.
        Does NOT change the STABLE pointer (safe experimentation).
        
        Scenarios:
        1. Fork whole version: Create a draft copy of history to edit manually.
        2. Fork specific option: In SCA, pick a rejected option to refine it.
        """
        pid = UUID(project_id)
        project = await self._get_project_or_fail(pid)
        node_state = project.nodes.get(node_id)
        if not node_state:
            raise ResourceNotFoundError("NodeState", node_id)

        # 1. Load Base Version (The Source)
        base_version = await self.v_repo.get(base_version_id)
        if not base_version:
            raise ResourceNotFoundError("NodeVersion", str(base_version_id))

        # 2. Construct Payload for New Draft
        new_outputs = []
        provenance = {
            "trigger": VersionTrigger.FORK.value,
            "parent_version_id": str(base_version_id),
            "source": "full_version"
        }

        if target_output_index is not None:
            # Slicing Strategy: Pick specific output (e.g. Option #3)
            if 0 <= target_output_index < len(base_version.outputs):
                # Deep copy the specific output
                target_out = base_version.outputs[target_output_index].model_copy(deep=True)
                target_out.is_selected = True  # It becomes the active candidate in the new draft
                new_outputs = [target_out]
                provenance["source"] = "single_output"
                provenance["source_index"] = target_output_index
            else:
                raise ValueError(f"Output index {target_output_index} out of bounds.")
        else:
            # Clone Strategy: Copy all outputs (Full state recovery)
            new_outputs = [o.model_copy(deep=True) for o in base_version.outputs]

        # 3. Create Draft Version (Immutable Record of the 'Fork')
        draft_version = NodeVersion(
            id=uuid4(),
            project_id=pid,
            node_id=node_id,
            created_at=datetime.utcnow(),
            outputs=new_outputs,
            provenance=provenance
        )
        await self.v_repo.create(draft_version)

        # 4. Update Node Pointer (Move 'Working' to this new branch)
        node_state.working_version_id = draft_version.id
        node_state.status = NodeStatus.REVIEWING
        node_state.updated_at = datetime.utcnow()

        # 5. Persist & Notify
        await self.p_repo.save(project)
        
        await self._emit(project_id, NodeStatusEvent(node_id, NodeStatus.REVIEWING))
        await self._emit(project_id, TimelineUpdateEvent(project_id))
        
        # Push the full draft data so the UI updates immediately
        version_dump = draft_version.model_dump(mode='json')
        await self._emit(project_id, NodeUpdateEvent(node_id, version_dump))
        
        logger.info(f"Forked node {node_id} from version {base_version_id} -> {draft_version.id}")

    async def restore_node(
        self, 
        project_id: str, 
        node_id: str, 
        version_id: UUID
    ) -> None:
        """
        Time Travel: Restores STABLE pointer.
        [REFACTORED] Non-Destructive Restore.
        Does NOT invalidate downstream. Does NOT auto-cascade.
        """
        pid = UUID(project_id)
        
        # 1. Perform Restore Transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                project = await self.p_repo.get(pid, session=session)
                if not project: 
                    raise ResourceNotFoundError("Project", str(pid))
                
                node_state = project.nodes.get(node_id)
                target_version = await self.v_repo.get(version_id, session=session)
                
                if not node_state or not target_version:
                    raise ResourceNotFoundError("Node/Version", f"{node_id}/{version_id}")

                # Update Pointers
                node_state.stable_version_id = version_id
                node_state.working_version_id = None 
                node_state.status = NodeStatus.COMMITTED
                node_state.updated_at = datetime.utcnow()

                # [REMOVED] Invalidate Downstream
                # await self.topo_service.invalidate_downstream(project, node_id)

                await self.p_repo.save(project, session=session)

        # 2. Notify
        await self._emit(project_id, NodeStatusEvent(node_id, NodeStatus.COMMITTED))
        await self._emit(project_id, TimelineUpdateEvent(project_id))
        
        version_dump = target_version.model_dump(mode='json')
        await self._emit(project_id, NodeUpdateEvent(node_id, version_dump))

        logger.info(f"Restored {node_id}. State updated.")

        # [REMOVED] Auto-Cascade
        # await self._cascade_to_next_node(pid, node_id)

    # [NEW] Centralized Cascade Logic
    async def _cascade_to_next_node(self, project_id: UUID, current_node_id: str, runtime: Optional[RuntimeConfig] = None):
        """
        Calculates and triggers the next node in the linear sequence.
        [REFACTORED] Conservative Cascade: Stops if next node is already active.
        Only cascades if next node is VOID (new) or LOCKED (waiting).
        """
        async with AsyncSessionLocal() as session:
            async with session.begin(): 
                project = await self.p_repo.get(project_id, session=session)
                
                # Use TopologyService to find linear successor
                next_node_id = self.topo_service.get_linear_successor(project, current_node_id)
                
                if not next_node_id:
                    logger.info(f"Pipeline end reached or waiting for expansion after {current_node_id}.")
                    return

                logger.info(f"Checking Cascade: {current_node_id} -> {next_node_id}")

                # [FIX] Lazy Initialization / Update
                base_id = next_node_id.split('-')[0] if '-' in next_node_id else next_node_id
                iter_idx = int(next_node_id.split('-')[1]) if '-' in next_node_id else None
                
                # Retrieve existing or create new
                next_node = project.nodes.get(next_node_id)
                if not next_node:
                    next_node = NodeState(
                        node_id=next_node_id,
                        base_id=base_id,
                        iteration_index=iter_idx,
                        status=NodeStatus.VOID
                    )
                    # Add to project.nodes dictionary for consistency
                    project.nodes[next_node_id] = next_node

                # [CRITICAL LOGIC CHANGE]
                # Conservative Propagation: Only run if VOID (New) or LOCKED (Waiting).
                # If it's already running, reviewing, committed, or failed -> STOP.
                if next_node.status not in [NodeStatus.VOID, NodeStatus.LOCKED]:
                    logger.info(f"🛑 Cascade Stopped: Next node {next_node_id} is already {next_node.status}.")
                    return
                
                logger.info(f"🚀 Auto-Cascading to {next_node_id}")

                # Set Status DRAFTING immediately
                next_node.status = NodeStatus.DRAFTING
                next_node.updated_at = datetime.utcnow()
                
                # DB Upsert
                await self.p_repo.update_node_state(str(project_id), next_node, session=session)

        # Notify UI (Timeline will update and show this new node because it's now active)
        await self._emit(str(project_id), NodeStatusEvent(next_node_id, NodeStatus.DRAFTING))
        await self._emit(str(project_id), TimelineUpdateEvent(str(project_id)))

        # Fire & Forget Execution
        run_cmd = RunNodeCommand(
            project_id=str(project_id),
            node_id=next_node_id,
            intent="generate",
            inputs={"auto_triggered": True}
        )
        self._dispatch_background_task(
            self.run_node(run_cmd, runtime=runtime),
            project_id=str(project_id),
            node_id=next_node_id
        )

    # --- Internal Background Worker ---

    async def _bg_run_task(
        self, 
        project_id: str, 
        effective_id: str, 
        blueprint: Any, 
        cmd: RunNodeCommand,
        intent: str,
        config: Dict[str, Any],
        trigger: VersionTrigger,
        parent_version_id: Optional[UUID],
        runtime: Optional[RuntimeConfig] = None
    ):
        """
        Executes the compute pipeline via NodeProcessor.
        Handles Context Injection for Iterative Intents (Refine/Critique).
        Includes Input Resolution for iterative nodes.
        
        [FIX Issue 1] Strictly isolate DB READ, COMPUTE (No DB), and DB WRITE phases.
        Prevents holding DB connections during long-running LLM calls.
        """
        pid = UUID(project_id)
        # effective_id passed as arg

        try:
            # --- 1. READ SNAPSHOT PHASE (Short-lived session) ---
            # Fetch Project and NodeState only. Detach them as Pydantic models.
            target_ver_id = None
            async with AsyncSessionLocal() as session:
                project = await self.p_repo.get(pid, session=session)
                if not project: 
                    logger.error(f"Project not found: {pid}")
                    return
                
                # [FIX] Fetch node value to avoid NameError
                node_state = project.nodes.get(effective_id)
                if not node_state:
                    logger.error(f"Node not found: {effective_id}")
                    return
                
                # We need to know which version to use as "Previous Output" if needed.
                # Capture it here to avoid re-opening the session just for this check.
                target_ver_id = parent_version_id or node_state.working_version_id or node_state.stable_version_id

            # --- 2. PREPARE CONTEXT (Asset Stratification) ---
            
            # [FIX] Smart Filter: Block artifacts for code nodes, Allow for reporting
            include_artifacts = False
            
            # Heuristic 1: Reporting Phase (Paper Engine needs figures for LaTeX compilation)
            if blueprint.phase_label and "Reporting" in blueprint.phase_label:
                include_artifacts = True
            
            # Heuristic 2: Native Paper Engine explicit check
            if blueprint.meta.get("executor_engine") == "native_paper_engine":
                include_artifacts = True
                
            if include_artifacts:
                logger.info(f"Context Injection: Full Mode (Reporting/Paper Engine) for {effective_id}")
            else:
                logger.info(f"Context Injection: Optimized Mode (Code/Data only) for {effective_id}")

            # A. Assemble Global Upstream Context with Filtering
            # [FIX] Unpack 4 values: Dormant assets are now separated
            context_str, active_manifest, dormant_assets, file_schemas = await self.ctx_service.build_history(
                project, 
                effective_id, 
                include_artifacts=include_artifacts
            )

            # [Rule Override] Merge Explicit Input Manifest
            # User explicitly provided these files in the request (e.g. initial upload),
            # so we MUST inject them regardless of safety filters.
            if "file_manifest" in cmd.inputs:
                active_manifest.update(cmd.inputs["file_manifest"])

            # [FIX] Alias 'manifest' to 'active_manifest' for backward compatibility 
            # with inputs_snapshot logic later in the function
            manifest = active_manifest

            # B. Resolve dynamic inputs (Context Slicing for Iterative Nodes)
            resolved_inputs = await self.resolver.resolve(project, blueprint, effective_id)
            
            # Merge with command inputs (Command takes precedence)
            user_input_payload = {
                "instruction": cmd.instruction or "",
                "inputs": {**resolved_inputs, **cmd.inputs}  # Command inputs override resolved
            }

            # C. Fetch Local Context (Read Working) - For Refine/Critique
            # If we really need previous output, we fetch it now.
            previous_output = None
            needs_history = intent in ["refine", "critique", "execute_only"]
            
            if needs_history and target_ver_id:
                async with AsyncSessionLocal() as session:
                    prev_version = await self.v_repo.get(target_ver_id, session=session)
                    if prev_version:
                        previous_output = prev_version.selected_output
            
            # Check for Execute-Only Deadlock (Logic check, no DB)
            if intent == "execute_only" and not previous_output:
                raise ValueError("Execute-Only failed: No source code found (Working or Stable). Please create a draft first.")
                
            # --- 3. COMPUTE PHASE (Long Running, No DB) ---
            # This is the heavy lifting. ABSOLUTELY NO DB connections should be open here.
            # Pass dormant_assets to processor for JIT injection
            outputs = await self.processor.process(
                project_id=project_id,
                blueprint=blueprint,
                context_str=context_str,
                file_manifest=active_manifest,  # Light files only
                user_input=user_input_payload,
                intent=intent,
                config=config,
                previous_output=previous_output,
                file_schemas=file_schemas,  # [FIX] Pass schemas
                runtime=runtime,  # [BYOK]
                dormant_manifest=dormant_assets  # [FIX] Pass heavy files for JIT
            )

            # --- Global Asset Registration (Fix 3.1) ---
            # Update Project.assets with any new files produced by this node.
            # Note: processor.process may return files that need to be registered in the ledger.
            new_assets_map = {}
            for output in outputs:
                for block in output.blocks:
                    if block.type == BlockType.FILE:
                        blob_hash = block.meta.get("blob_hash")
                        filename = block.label
                        if blob_hash and filename:
                            virtual_path = f"history/{effective_id}/{filename}"
                            new_assets_map[virtual_path] = blob_hash
                            block.meta["virtual_path"] = virtual_path

            if new_assets_map:
                # Quick write transaction for assets
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        p = await self.p_repo.get(pid, session=session)
                        if p:
                            p.assets.update(new_assets_map)
                            await self.p_repo.save(p, session=session)
                
                # Update both active_manifest and manifest alias
                active_manifest.update(new_assets_map)
                manifest.update(new_assets_map)
                logger.info(f"Registered {len(new_assets_map)} new global assets from {effective_id}")

            # --- 4. WRITE RESULT PHASE (Short-lived session) ---
            # [FIX Issue 1] Default selection logic moved to node_processor.py
            if outputs and not any(o.is_selected for o in outputs):
                is_sca_node = blueprint.interaction and blueprint.interaction.can_select_alternatives
                if not is_sca_node:
                    outputs[-1].is_selected = True
            
            # Build Input Snapshot
            inputs_snapshot = {
                "instruction": cmd.instruction or "",
                "inputs": cmd.inputs,
                "file_manifest": manifest,  # Uses the aliased/updated manifest
                "intent": intent
            }
            
            new_version = NodeVersion(
                id=uuid4(),
                project_id=pid,
                node_id=effective_id,
                created_at=datetime.utcnow(),
                outputs=outputs,
                provenance={
                    "trigger": trigger.value,
                    "intent": intent,
                    "parent_version_id": str(parent_version_id) if parent_version_id else None,
                    "inputs_snapshot": inputs_snapshot
                }
            )
            
            # Persist Data
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Save version
                    await self.v_repo.create(new_version, session=session)

                    # Determine Success/Failure based on exit_code
                    is_success = True
                    exit_code = 0
                    if new_version.outputs:
                        out = new_version.selected_output
                        if out:
                            exit_code = out.metadata.get("exit_code", 0)
                            if exit_code != 0:
                                is_success = False

                    # Determine Next Status
                    next_status = NodeStatus.REVIEWING if is_success else NodeStatus.FAILED
                    
                    # Update Project Node State
                    ns = NodeState(
                        node_id=effective_id, base_id=node_state.base_id,
                        iteration_index=node_state.iteration_index,
                        status=next_status, 
                        working_version_id=new_version.id,
                        stable_version_id=node_state.stable_version_id,
                        updated_at=datetime.utcnow()
                    )
                    await self.p_repo.update_node_state(pid, ns, session=session)

            # E. Notify
            version_dump = new_version.model_dump(mode='json')
            await self._emit(project_id, NodeUpdateEvent(effective_id, version_dump))
            
            # Emit status update
            await self._emit(project_id, NodeStatusEvent(effective_id, next_status))
            
            if not is_success:
                 # Extract Error for UI
                 error_msg = f"Node execution failed (Exit Code: {exit_code})"
                 
                 # [REFACTOR] 直接获取语义错误，移除所有防御性 get_block 链
                 error_content = new_version.selected_output.get_primary_error()
                 
                 if error_content:
                     content_str = error_content
                     detail = content_str[:800] + "..." if len(content_str) > 800 else content_str
                     error_msg += f"\n\nDetails: {detail}"

                 await self._emit(project_id, ErrorEvent(error_msg))

        except Exception as e:
            logger.error(f"Background Task Failed for {effective_id}: {e}", exc_info=True)
            # [FIX] Force FAILED state broadcast on system panic
            await self._emit(project_id, NodeStatusEvent(effective_id, NodeStatus.FAILED))
            await self._emit(project_id, ErrorEvent(str(e)))
            
            # [FIX] Force DB update to FAILED state to prevent hanging UI
            try:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        # Re-fetch project to get the specific node state
                        p = await self.p_repo.get(pid, session=session)
                        if p and effective_id in p.nodes:
                            p.nodes[effective_id].status = NodeStatus.FAILED
                            p.nodes[effective_id].updated_at = datetime.utcnow()
                            await self.p_repo.update_node_state(str(pid), p.nodes[effective_id], session=session)
            except Exception as db_err:
                logger.error(f"Failed to update broken state to DB: {db_err}")

    # [NEW] Vectorized Batch Update Implementation with Write-Behind
    async def batch_update_draft_content(self, project_id: str, node_id: str, edits: Dict[str, Any], force_flush: bool = False):
        """
        Efficiently updates multiple blocks in the current working draft.
        [ENHANCED] Write-Behind Pattern: Writes to Redis Hash first, flushes to DB on demand.
        
        Args:
            project_id: Project UUID
            node_id: Node Identifier
            edits: Dictionary mapping BlockID -> NewContent
            force_flush: If True, immediately flush to DB (bypasses Write-Behind)
        """
        if not edits:
            return

        # Write-Behind: Write to Redis Hash first (unless force_flush)
        if not force_flush and self.redis_client:
            try:
                draft_key = self._get_draft_key(project_id, node_id)
                # Store edits as JSON in Redis Hash
                pipeline = self.redis_client.pipeline()
                for block_id, content in edits.items():
                    pipeline.hset(draft_key, block_id, json.dumps(content))
                # Set TTL (1 hour)
                pipeline.expire(draft_key, 3600)
                await pipeline.execute()
                
                logger.debug(f"Write-Behind: Stored {len(edits)} edits in Redis for node {node_id}")
                
                # Still emit event for immediate UI update (optimistic)
                # Note: The actual DB write will happen on flush
                await self._emit(project_id, NodeUpdateEvent(node_id, {"status": "draft_updated"}))
                return
            except Exception as e:
                logger.warning(f"Write-Behind failed, falling back to direct DB write: {e}")

        # Fallback: Direct DB write (if Redis unavailable or force_flush)
        pid = UUID(project_id)
        project = await self._get_project_or_fail(pid)
        node_state = project.nodes.get(node_id)
        
        if not node_state or not node_state.working_version_id:
            raise StateError("No working draft available to edit.")

        # 1. Load Heavy Version ONCE
        version = await self.v_repo.get(node_state.working_version_id)
        if not version:
            raise ResourceNotFoundError("NodeVersion", str(node_state.working_version_id))

        updated_count = 0
        
        # 2. Define Recursive Updater
        def update_blocks_recursive(blocks):
            nonlocal updated_count
            for block in blocks:
                # Direct Match
                if block.id in edits:
                    # Only update if content actually changed (Simple check)
                    # For objects, this might be expensive, but safe enough here
                    new_val = edits[block.id]
                    # Handle "Empty" from frontend potentially being empty string vs None
                    if new_val is not None: 
                        block.content = new_val
                        if "edited" not in block.tags:
                            block.tags.append("edited")
                        updated_count += 1
                
                # Recurse
                if block.children:
                    update_blocks_recursive(block.children)

        # 3. Apply Updates to ALL Outputs (Handling SCA scenarios)
        if version.outputs:
            for output in version.outputs:
                update_blocks_recursive(output.blocks)

        # 4. Save ONCE if needed
        if updated_count > 0:
            await self.v_repo.update_draft(version)
            logger.info(f"Batch updated {updated_count} blocks for node {node_id} (direct DB write)")
            
            # Emit ONCE
            version_dump = version.model_dump(mode='json')
            await self._emit(project_id, NodeUpdateEvent(node_id, version_dump))
        else:
            logger.debug(f"Batch update called but no matching blocks found (Edits: {list(edits.keys())})")

    # [DEPRECATED / WRAPPER] Kept for backward compatibility
    async def update_draft_content(self, project_id: str, node_id: str, block_id: str, content: Any):
        """
        Legacy scalar update. Wraps batch_update_draft_content.
        """
        await self.batch_update_draft_content(project_id, node_id, {block_id: content})

    async def select_and_converge(self, project_id: str, node_id: str, index: int):
        """
        [Convergence Strategy]
        Creates a NEW Version containing ALL options, but with the specific index selected.
        This preserves the history of rejected options.
        """
        pid = UUID(project_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                project = await self.p_repo.get(pid, session=session)
                node_state = project.nodes.get(node_id)
                
                current_ver = await self.v_repo.get(node_state.working_version_id, session=session)
                if not (0 <= index < len(current_ver.outputs)):
                    raise ValueError(f"Option index {index} out of bounds.")

                # [FIX Issue 3] Non-Destructive Convergence
                # Deep copy ALL outputs to preserve the full option set in history
                new_outputs = [o.model_copy(deep=True) for o in current_ver.outputs]
                
                # Update selection state
                for i, out in enumerate(new_outputs):
                    out.is_selected = (i == index)
                
                # Create New Converged Version
                new_version = NodeVersion(
                    id=uuid4(),
                    project_id=pid,
                    node_id=node_id,
                    created_at=datetime.utcnow(),
                    outputs=new_outputs, # Keep all options
                    provenance={
                        "trigger": VersionTrigger.SELECT.value,
                        "parent_version_id": str(current_ver.id),
                        "source_index": index
                    }
                )
                await self.v_repo.create(new_version, session=session)

                # Update Pointer
                node_state.working_version_id = new_version.id
                node_state.updated_at = datetime.utcnow()
                await self.p_repo.update_node_state(str(pid), node_state, session=session)

        # Notify
        await self._emit(project_id, NodeUpdateEvent(node_id, new_version.model_dump(mode='json')))
        await self._emit(project_id, TimelineUpdateEvent(project_id))

    async def select_and_commit(
        self, 
        project_id: str, 
        node_id: str, 
        index: int,
        updated_content: Any = None,  # [NEW] Optional content injection
        block_id: str = None          # [NEW] Target block for update
    ):
        """
        [FIX] Atomic Selection & Commitment.
        Updates selection, (Optionally updates content), Commits, Expands Topology, and Cascades.
        """
        logger.info(f"Select & Commit for Node {node_id}, Option {index}")
        
        # 1. (Optional) Atomic Update if content provided
        if updated_content is not None and block_id:
            logger.info(f"Atomic update detected for block {block_id}")
            # Ensure the draft is updated with the latest user edits BEFORE selecting
            await self.update_draft_content(project_id, node_id, block_id, updated_content)

        # 2. Perform Selection (Converge to new version)
        await self.select_and_converge(project_id, node_id, index)
        
        # 3. Perform Commit (reuse commit_node logic)
        cmd = CommitNodeCommand(project_id=project_id, node_id=node_id)
        await self.commit_node(cmd)

    # [FIX ISSUE 5] New Helper for Reset
    async def reset_node(self, project_id: str, node_id: str) -> None:
        """
        Hard Reset a node to VOID state.
        [REFACTORED] Does NOT invalidate downstream.
        """
        pid = UUID(project_id)
        logger.info(f"Resetting node {node_id} to VOID")
        
        async with AsyncSessionLocal() as session:
            async with session.begin():
                project = await self.p_repo.get(pid, session=session)
                if not project: raise ResourceNotFoundError("Project", str(pid))
                
                node_state = project.nodes.get(node_id)
                if not node_state: raise ResourceNotFoundError("NodeState", node_id)
                
                # 1. Clear State
                node_state.status = NodeStatus.VOID
                node_state.working_version_id = None
                node_state.updated_at = datetime.utcnow()
                
                # [REMOVED] Invalidate Downstream
                # await self.topo_service.invalidate_downstream(project, node_id)
                
                # 3. Persist everything
                await self.p_repo.save(project, session=session)

        # 4. Notify Frontend
        await self._emit(project_id, NodeStatusEvent(node_id, NodeStatus.VOID))
        await self._emit(project_id, TimelineUpdateEvent(project_id))

    # --- Helpers ---

    def _extract_list_from_output(self, output) -> List[Any]:
        """Extracts list items from node output for topology expansion."""
        if not output:
            return []
        for b in output.blocks:
            if isinstance(b.content, dict):
                # Try common list keys
                for key in ["sub_problem_list", "flat_task_list", "items"]:
                    if key in b.content and isinstance(b.content[key], list):
                        return b.content[key]
            elif isinstance(b.content, list):
                return b.content
        return []

    async def _hydrate_assets(self, pid: UUID, manifest: dict):
        """Registers assets in the project's global asset store."""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                p = await self.p_repo.get(pid, session=session)
                if p:
                    p.assets.update(manifest)
                    p.assets = dict(p.assets)
                    await self.p_repo.save(p, session=session)

    async def _get_project_or_fail(self, pid: UUID) -> Project:
        p = await self.p_repo.get(pid)
        if not p:
            raise ResourceNotFoundError("Project", str(pid))
        return p

    async def _emit(self, project_id: str, event: Any):
        # Event is a Pydantic DomainEvent model
        # Channel format: "project:{project_id}" for consistency
        channel = f"project:{project_id}"
        event_dict = event.model_dump(mode='json')
        await self.bus.publish(channel, event_dict["event"], event_dict["data"])

    def _find_block_by_id(self, blocks: list, target_id: str):
        """Find a block by ID recursively."""
        for b in blocks:
            if b.id == target_id:
                return b
            if b.children:
                found = self._find_block_by_id(b.children, target_id)
                if found:
                    return found
        return None

    # [OPTIMIZATION] 增强后台任务的安全性
    def _dispatch_background_task(self, coro, project_id: str = None, node_id: str = None):
        """
        创建一个带有异常捕获回调的后台任务。
        防止后台任务失败后无日志、无状态更新。
        [FIX] 添加上下文信息以便在失败/取消时恢复状态。
        """
        task = asyncio.create_task(coro)
        
        # Attach context metadata
        if project_id and node_id:
            task.project_id = project_id
            task.node_id = node_id
            
        task.add_done_callback(self._handle_background_task_result)
    
    def _handle_background_task_result(self, task: asyncio.Task):
        project_id = getattr(task, "project_id", None)
        node_id = getattr(task, "node_id", None)

        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning(f"Background task was cancelled (Project: {project_id}, Node: {node_id})")
            if project_id and node_id:
                asyncio.create_task(self._finalize_failed_state(project_id, node_id, "Task Cancelled (Timeout or Shutdown)"))
        except Exception as e:
            logger.error(f"Background task failed unexpectedly: {e}", exc_info=True)
            if project_id and node_id:
                asyncio.create_task(self._finalize_failed_state(project_id, node_id, str(e)))

    async def _finalize_failed_state(self, project_id: str, node_id: str, error_msg: str):
        """
        [FIX] 兜底状态恢复机制。
        当任务因 CancelledError 或未捕获异常崩溃时，强制将节点状态置为 FAILED。
        """
        try:
            pid = UUID(project_id)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # 重新获取项目和节点，确保状态是最新的
                    project = await self.p_repo.get(pid, session=session)
                    if project and node_id in project.nodes:
                        node = project.nodes[node_id]
                        # 仅当状态处于中间态时才覆写，避免覆盖后续可能的合法状态（虽然不太可能）
                        if node.status in [NodeStatus.DRAFTING, NodeStatus.LOCKED, NodeStatus.VOID]:
                            node.status = NodeStatus.FAILED
                            node.updated_at = datetime.utcnow()
                            await self.p_repo.update_node_state(str(pid), node, session=session)
                            logger.info(f"Force-set node {node_id} to FAILED due to task abort.")

            # 发送事件通知前端
            await self._emit(project_id, NodeStatusEvent(node_id, NodeStatus.FAILED))
            await self._emit(project_id, ErrorEvent(f"System Error: {error_msg}"))
        except Exception as e:
            logger.error(f"Failed to recover zombie node {node_id}: {e}", exc_info=True)
