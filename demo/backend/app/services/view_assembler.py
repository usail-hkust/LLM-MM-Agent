"""
View Assembler - The UI Brain.

[Updated]
- Removed absolute URL injection (Security Fix).
- Ensures 'virtual_path' metadata is present for File blocks.
- Relative paths in Markdown are left untouched for frontend resolution.
- [FIX] Deterministic Block ID Generation for stable UI identity.
- [FIX] Logic for 'select_and_commit' action.
- [CRITICAL FIX] SCA Card ID Alignment: Reuse DB Block ID instead of synthetic ID to fix Save/Edit.
- [ARCH FIX] Layout Downgrade Strategy: Decoupled from Status, Added LOG_CONSOLE support.
- [OPTIMIZATION] SCA Card Content: Sanitized titles and removed truncation.
- [CRITICAL FIX] SCA Anchor Resolution: Implemented Multi-Priority Strategy to strictly prefer CODE/DATA over MARKDOWN noise.
"""
import logging
import uuid
import re
from typing import List, Optional
from uuid import UUID

from datetime import datetime
from app.core.definitions import (
    NodeStatus, LayoutMode, BlockType, RenderType, ActionType, SystemTags, ActionScope
)
from app.utils.files import guess_mime_type # [FIX] Add guess_mime_type
from app.domain.models import Project, NodeState, NodeVersion
from app.domain.blueprints import NodeBlueprint, InteractionPolicy
from app.domain.unified_io import ContentBlock, RenderAction, NodeOutput, ActionInputSpec
from app.api.schemas import NodeWorkspaceView, NodeDefinitionView, NodeStateView

logger = logging.getLogger(__name__)


class ViewAssembler:
    """
    Constructs the 'Unified Node Envelope'.
    Decouples Persistence (DB) from Presentation (UI).
    """

    def assemble(
        self, 
        project: Project, 
        node_id: str, 
        blueprint: NodeBlueprint,
        version: Optional[NodeVersion]
    ) -> NodeWorkspaceView:
        
        node_state = project.nodes.get(node_id) if project.nodes else None
        current_status = node_state.status if node_state else NodeStatus.VOID
        
        effective_output: Optional[NodeOutput] = None
        if version:
            effective_output = version.selected_output
            
        # 1. [Dynamic Layout Synthesizer]
        layout = blueprint.ux.layout_mode
        
        # Strategy A: Layout Downgrade (Fix "Blank Right Panel")
        # If configured as WORKBENCH (Split) but no secondary content (Logs/Artifacts) exists yet,
        # degrade to FOCUS (Single Column) to let the editor take full width.
        if layout == LayoutMode.WORKBENCH and effective_output:
            has_secondary_content = False
            for b in effective_output.blocks:
                # Check for Files, Images, Charts, OR CONSOLE/LOGS
                # [FIX] Added LOG_CONSOLE to prevent layout collapse for executor nodes (like 1.2) 
                # that only produce text/logs but still need a split view.
                if b.type == BlockType.FILE or \
                   b.render_type == RenderType.ARTIFACT_GALLERY or \
                   b.render_type == RenderType.LOG_CONSOLE or \
                   (b.type == BlockType.DATA and b.render_type == RenderType.DATA_VIEWER):
                    has_secondary_content = True
                    break
            
            # [FIX] Decoupled from Status.
            # If a Workbench node produces absolutely no secondary content, degrade to Focus.
            # This ensures consistent layout regardless of whether the node is REVIEWING or COMMITTED.
            if not has_secondary_content:
                layout = LayoutMode.FOCUS

        # [FIX Issue 4] Robust Selection Mode Activation
        # Determine if we should use the Selection View (Cards) based on STATIC Blueprint config,
        # not just transient runtime state.
        is_sca_view = (
            blueprint.interaction.can_select_alternatives or
            blueprint.ux.primary_view in [RenderType.SCA_OPTION_CARD, RenderType.SCA_PLAN_CARD]
        )

        # 2. Permission & Hydration
        # Read-only if committed, locked, OR if we are viewing a historical version (not the active working draft)
        is_history_view = False
        if version and node_state and node_state.working_version_id:
            if version.id != node_state.working_version_id:
                is_history_view = True

        is_read_only = (
            current_status == NodeStatus.COMMITTED or 
            current_status == NodeStatus.LOCKED or 
            is_history_view
        )
        blocks = []
        metadata = {}
        global_actions = []

        if version:
            # Use Selection layout if configured, regardless of current status
            if is_sca_view and version.outputs:
                layout = LayoutMode.SELECTION
                # Pass all outputs (options) to the builder, not just the selected one
                blocks = self._build_selection_blocks(
                    version.outputs, 
                    node_id, 
                    blueprint, 
                    version.id,
                    is_read_only # [FIX] Pass read-only flag
                )
                # Extract metadata from selected output if available
                if effective_output:
                    metadata = effective_output.metadata
            elif effective_output:
                # Clone blocks to avoid mutation
                raw_blocks = [b.model_copy(deep=True) for b in effective_output.blocks]
                metadata = effective_output.metadata

                # A. Inject Component Actions (Scoped BLOCK)
                blocks = self._inject_local_actions(
                    blocks=raw_blocks,
                    status=current_status,
                    policy=blueprint.interaction,
                    node_id=node_id,
                    is_read_only=is_read_only
                )
                
                # B. Inject Binding Keys
                blocks = self._inject_interaction_state(blocks, current_status, blueprint.interaction)
                
                # C. [FIX] Resolve Virtual Paths (Do NOT inject absolute URLs)
                self._resolve_virtual_paths(blocks, node_id)

                # D. [Unified Narrative Stream] Inject Console with Thought
                # Even if stdout is empty, this injects the thought process to avoid empty log state.
                if blueprint.ux.show_console:
                    blocks = self._inject_console(blocks, node_id, effective_output.thought or "")

                # E. [Control Plane Elevation] Build Global Actions
                # Instead of creating a fake footer block, we populate global_actions
                global_actions = self._build_global_actions(
                    status=current_status,
                    policy=blueprint.interaction,
                    node_id=node_id,
                    is_read_only=is_read_only
                )

        return NodeWorkspaceView(
            definition=NodeDefinitionView(
                id=blueprint.id, title=blueprint.title, type=blueprint.node_type, ux=blueprint.ux
            ),
            state=NodeStateView(
                status=current_status,
                layout_mode=layout, # Dynamically calculated
                blocks=blocks,
                global_actions=global_actions, # [NEW]
                metadata=metadata,
                is_read_only=is_read_only,
                active_version_id=version.id if version else None
            )
        )

    def _inject_local_actions(self, blocks, status, policy, node_id, is_read_only):
        if is_read_only: return blocks
        
        decorated = []
        for block in blocks:
            if block.children:
                block.children = self._inject_local_actions(block.children, status, policy, node_id, is_read_only)
            
            suffix = f"::{block.id}" if block.id else ""
            
            # [FIX] Scoped Actions: Set scope="BLOCK"
            # These will be rendered in the Atom header, NOT the Dock
            if block.type == BlockType.CODE and policy.can_reexecute:
                block.actions.append(RenderAction(
                    id=f"run_code{suffix}", label="Run Code", type=ActionType.PRIMARY, icon="Play",
                    scope=ActionScope.BLOCK, 
                    # [FIX] Include block_id explicitly for AtomShell consistency
                    # This enables the Atomic Save-before-Run logic in the backend
                    payload={
                        "action": "run_node", 
                        "node_id": node_id, 
                        "use_editor_content": True, 
                        "intent": "execute_only",
                        "block_id": block.id  # <--- Critical for resolving manual_content target
                    }
                ))

            if policy.can_edit_content and block.type in (BlockType.CODE, BlockType.MARKDOWN):
                block.actions.append(RenderAction(
                    id=f"save_draft{suffix}", label="Save", type=ActionType.SECONDARY, icon="Save",
                    scope=ActionScope.BLOCK,
                    validation_rule="require_dirty",
                    payload={"action": "save_draft", "node_id": node_id, "block_id": block.id}
                ))

            if block.render_type == RenderType.IDE_WORKSPACE and policy.can_reexecute:
                block.actions.append(RenderAction(
                    id=f"compile_ide{suffix}",
                    label="Compile & Fix",
                    type=ActionType.PRIMARY,
                    icon="Play",
                    scope=ActionScope.BLOCK,
                    payload={
                        "action": "run_node",
                        "node_id": node_id,
                        "intent": "compile",
                        "inputs": {"collect_ide_state": True},
                    }
                ))
            
            decorated.append(block)
        return decorated

    def _inject_interaction_state(
        self,
        blocks: List[ContentBlock],
        status: NodeStatus,
        policy: InteractionPolicy
    ) -> List[ContentBlock]:
        """
        [CRITICAL FIX] Calculates and injects 'data_key' for two-way binding.
        Recursive function that modifies blocks in-place (assumes they are already clones).
        """
        # Determine global editability based on Status and Policy
        # Only Reviewing state allows editing, provided policy permits it.
        is_globally_editable = (status == NodeStatus.REVIEWING) and policy.can_edit_content
        
        for block in blocks:
            # 1. Recurse for containers
            if block.children:
                self._inject_interaction_state(block.children, status, policy)
            
            # 2. Determine Block Editability
            # Only Content Blocks (Code, Markdown, Data) are editable
            # Files and Containers are structural/read-only
            if is_globally_editable and block.type in (BlockType.CODE, BlockType.MARKDOWN, BlockType.DATA):
                # Bind to ID. This tells the frontend: 
                # "This block is editable, and its value lives at 'new_content.{block.id}'"
                block.data_key = block.id
            else:
                # Explicitly disable editing
                block.data_key = None
                
        return blocks

    def _resolve_virtual_paths(self, blocks: List[ContentBlock], node_id: str):
        """
        [FIX] Ensures blocks have 'virtual_path' meta so frontend can construct authenticated URLs.
        Replaces previous logic that injected absolute http://... URLs.
        """
        for block in blocks:
            # Recursion
            if block.children:
                self._resolve_virtual_paths(block.children, node_id)
            
            if block.type == BlockType.FILE:
                # [FIX] Always ensure mime_type is present for frontend identification
                if not block.meta.get("mime_type") and block.label:
                    block.meta["mime_type"] = guess_mime_type(block.meta.get("filename", block.label))

                # If virtual_path missing, construct default based on node context
                if not block.meta.get("virtual_path") and block.label:
                    filename = block.meta.get("filename", block.label)
                    block.meta["virtual_path"] = f"history/{node_id}/{filename}"

                # Ensure we also provide 'remote_path' alias which frontend useBlobUrl looks for
                if block.meta.get("virtual_path"):
                    block.meta["remote_path"] = block.meta["virtual_path"]

    def _inject_console(self, blocks: List[ContentBlock], node_id: str, thought: str = "") -> List[ContentBlock]:
        """
        [Unified Narrative Stream]
        Consolidates Logs and Thoughts into a single SmartConsole block.
        """
        clean_blocks = []
        log_entries = []
        
        # 1. Inject Thought as the "Zero" Log
        if thought:
            log_entries.append({
                "id": f"thought-{node_id}",
                "type": SystemTags.THOUGHT,
                "content": thought,
                "timestamp": 0 
            })

        # 2. Collect existing logs
        for b in blocks:
            tags = set(b.tags or [])
            is_log = (tags & SystemTags.ALL_LOGS) or (b.label in ["Stderr", "Stdout", "Console Errors", "Runtime Error", "Execution Error", "Console Output"])
            
            if is_log:
                content_str = str(b.content)
                log_type = "stderr" if ("stderr" in tags or "error" in tags or "Error" in b.label) else "stdout"
                log_entries.append({
                    "id": b.id or str(uuid.uuid4()),
                    "type": log_type,
                    "content": content_str,
                    "timestamp": datetime.utcnow().timestamp() * 1000 
                })
            else:
                clean_blocks.append(b)
                
        # 3. Create Console Block
        console_block = ContentBlock(
            id=f"console::{node_id}",
            type=BlockType.DATA,
            render_type=RenderType.LOG_CONSOLE,
            label="Execution Console",
            content=log_entries, 
            tags=[SystemTags.EXECUTION_LOGS],
            meta={"expanded": True}
        )
        
        clean_blocks.append(console_block)
        return clean_blocks

    def _generate_deterministic_id(self, version_id: UUID, seed_key: str) -> str:
        """
        [FIX] Generates a stable Block ID using UUIDv5 based on Version and Key.
        Ensures that React components don't remount when the same content is re-rendered.
        """
        # Create a unique namespace for this version
        # We can't use UUID(version_id) directly if it's already a UUID object
        ns = version_id if isinstance(version_id, UUID) else UUID(str(version_id))
        return str(uuid.uuid5(ns, seed_key))

    def _build_selection_blocks(
        self, 
        outputs: List[NodeOutput], 
        node_id: str, 
        blueprint: NodeBlueprint,
        version_id: UUID,
        is_read_only: bool # [FIX] Added arg
    ) -> List[ContentBlock]:
        """
        Converts multiple NodeOutputs into a list of interactable Option Blocks.
        [CRITICAL FIX] Implemented Multi-Priority Anchor Resolution to prevent Markdown noise.
        [OPTIMIZATION] Sanitizes "thought" content by removing "# Option N: ..." prefixes.
        """
        option_blocks = []
        
        # Decide the Card Component based on blueprint configuration
        # Default to Option Card (Read-Only/Simple), fallback to Plan Card if configured
        target_render_type = blueprint.ux.primary_view or RenderType.SCA_OPTION_CARD
        
        # Regex to strip the "Option N: Title" header from the description
        # Matches: # Option 1: Title text... (newline)
        header_pattern = re.compile(r"^#\s*Option\s*\d+:\s*(.*?)(?:\n|$)", re.IGNORECASE)

        for idx, output in enumerate(outputs):
            # 1. Extract Description and Title from Thought
            raw_thought = output.thought or ""
            
            # [OPTIMIZATION] Intelligent Sanitization
            # Check if the thought starts with the prompt protocol header
            match = header_pattern.match(raw_thought)
            
            if match:
                # Extracted title from content
                extracted_title = match.group(1).strip()
                # Remove the header line to get clean description
                description = raw_thought[match.end():].strip()
                
                # Use extracted title if available, otherwise fallback to metadata or default
                title = extracted_title if extracted_title else output.metadata.get("title", f"Option {idx + 1}")
            else:
                # No header match -> Use raw thought
                description = raw_thought
                # Try finding an "Explanation" block fallback
                if not description:
                    expl_block = output.get_block("Explanation")
                    if expl_block and expl_block.content:
                        description = str(expl_block.content)
                    elif output.blocks and output.blocks[0].type == BlockType.MARKDOWN:
                        description = str(output.blocks[0].content)
                
                title = output.metadata.get("title", f"Option {idx + 1}")

            # [OPTIMIZATION] Removed Truncation
            # Pass the full description to the frontend
            description_full = description
            
            # [CRITICAL FIX] Multi-Priority Anchor Block Resolution (Source of Truth)
            # The goal is to find the MOST VALUABLE block to represent the option.
            # We strictly avoid selecting parser-generated Markdown noise (Thoughts).
            
            anchor_block = None
            
            # Priority 1: Semantic Labels (Business Logic)
            # Targets specific known keys from blueprints that represent the "Answer"
            target_labels = [
                "outline", "sub_problem_list", "paper_blueprint", 
                "paper_plan", "latex_source", "json", "code"
            ]
            for label in target_labels:
                anchor_block = output.get_block(label)
                if anchor_block: break
            
            # Priority 2: Structured Content (DATA > CODE > FILE)
            # If no semantic label matched, look for the first significant payload.
            # This ensures we pick the Code block in an Executor even if labeled "script.py".
            if not anchor_block:
                for b_type in [BlockType.DATA, BlockType.CODE, BlockType.FILE]:
                    for b in output.blocks:
                        if b.type == b_type:
                            anchor_block = b
                            break
                    if anchor_block: break
            
            # Priority 3: Fallback to Markdown (Strict Filtering of Parser Noise)
            # Parser adds "Explanation", "Thinking", or "Thought" as noise blocks. 
            # We only pick a markdown block if it seems to be content (NOT labeled as noise).
            if not anchor_block:
                for b in output.blocks:
                    if b.type == BlockType.MARKDOWN:
                        # Check against known noise labels from output_parsers.py
                        is_noise = b.label in ["Explanation", "Thinking", "Thought"]
                        if not is_noise:
                            anchor_block = b
                            break
            
            # Priority 4: Absolute Fallback
            # If everything else fails (e.g. only thinking exists), we must show something to avoid empty card.
            if not anchor_block and output.blocks:
                anchor_block = output.blocks[0]

            # [CRITICAL] Identity Assignment
            # If we found an anchor block with a valid ID, use it.
            # This links the transient "Card" to the persistent "Data Block".
            if anchor_block and anchor_block.id:
                active_block_id = anchor_block.id
                content_payload = anchor_block.content
                is_editable = not is_read_only
            else:
                # Last Resort: If output is empty or structureless, use deterministic fallback.
                # Note: Edits must be disabled when no persistent anchor exists.
                if not is_read_only:
                    logger.warning(f"SCA Option {idx}: Missing persistent anchor. Rendering read-only.")
                active_block_id = self._generate_deterministic_id(version_id, f"option_{idx}")
                content_payload = output.to_context_dict()
                is_editable = False

            # Define Actions (Only if NOT read-only)
            actions = []
            if not is_read_only:
                # 1. Select Action
                select_action = RenderAction(
                    id=f"select_opt_{idx}",
                    label="SELECT" if target_render_type == RenderType.SCA_PLAN_CARD else "Select This",
                    type=ActionType.PRIMARY if not output.is_selected else ActionType.SECONDARY,
                    payload={
                        # [FIX] New atomic action
                        "action": "select_and_commit", 
                        "node_id": node_id, 
                        "option_index": idx,
                        # Pass the active ID so select_and_commit can perform atomic update
                        "block_id": active_block_id 
                    },
                    confirm_message="Select this option and proceed to the next step?"
                )
                actions.append(select_action)

                # 2. Save Action (Only for editable Plan Cards)
                if target_render_type == RenderType.SCA_PLAN_CARD and is_editable:
                    actions.append(RenderAction(
                        id=f"save_plan_{idx}",
                        label="SAVE",
                        type=ActionType.SECONDARY,
                        icon="Save",
                        validation_rule="require_dirty",
                        # [FIX] block_id matches the DB ID (active_block_id)
                        payload={"action": "save_draft", "node_id": node_id, "block_id": active_block_id}
                    ))

            # Create Card Block
            card = ContentBlock(
                id=active_block_id, # [CRITICAL] Use Real ID to align with DB
                type=BlockType.DATA,
                label=title,
                content=content_payload,
                render_type=target_render_type,
                meta={
                    "is_selected": output.is_selected,
                    "analysis": output.metadata.get("analysis", ""),
                    "title": title,
                    "description": description_full, # [FIX] Use full text
                    "status": output.metadata.get("status", "ACTIVE") # Support Rejected visual state
                },
                actions=actions,
                # [CRITICAL] Bind for editing ONLY if Plan Card AND Not Read Only
                # This ensures the frontend hook receives the correct DB ID as the binding key
                data_key=active_block_id if (target_render_type == RenderType.SCA_PLAN_CARD and is_editable) else None
            )

            option_blocks.append(card)
            
        # Add Global Actions Footer (Only if NOT read-only)
        if not is_read_only:
            footer = ContentBlock(
                type=BlockType.MARKDOWN,
                label="Actions",
                content="",
                actions=[
                    RenderAction(
                        id="reject_all",
                        label="Reject & Regenerate All",
                        type=ActionType.DANGER,
                        icon="RefreshCcw",
                        input_spec=ActionInputSpec(
                            type="text", 
                            label="Feedback for regeneration", 
                            key="feedback", 
                            required=True,
                            default_value="Please provide more diverse options."
                        ),
                        payload={"action": "reject_node", "node_id": node_id}
                    )
                ]
            )
            option_blocks.append(footer)
            
        return option_blocks

    def _build_global_actions(self, status, policy, node_id, is_read_only) -> List[RenderAction]:
        """Generates Global Workspace Actions (Approve/Reject)."""
        actions = []
        if is_read_only: return actions
        
        if status == NodeStatus.REVIEWING and policy.approval_required:
            actions.append(RenderAction(
                id="approve", label="Approve", type=ActionType.PRIMARY, icon="Check", 
                scope=ActionScope.WORKSPACE,
                payload={"action": "approve_node", "node_id": node_id}
            ))
            actions.append(RenderAction(
                id="reject", label="Reject", type=ActionType.DANGER, icon="RefreshCcw", 
                scope=ActionScope.WORKSPACE,
                input_spec=ActionInputSpec(type="text", label="Reason", key="feedback", required=True), 
                payload={"action": "reject_node", "node_id": node_id}
            ))
        return actions
