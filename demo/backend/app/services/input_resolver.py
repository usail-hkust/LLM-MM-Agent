"""
Input Resolver Service.

Responsible for resolving dynamic inputs, context slicing, and provenance injection.
Handles the complexity of fetching dependencies and slicing lists for iterative nodes.
"""
import logging
from typing import Dict, Any

from app.domain.models import Project
from app.domain.blueprints import NodeBlueprint
from app.infra.persistence.repositories import VersionRepository


logger = logging.getLogger(__name__)


class InputResolver:
    """
    Resolves implicit inputs for a node execution.
    Handles:
    1. Context Slicing (Iterative Nodes).
    2. System Context injection.
    """

    def __init__(self, version_repo: VersionRepository):
        self.v_repo = version_repo

    async def resolve(
        self, 
        project: Project, 
        blueprint: NodeBlueprint, 
        node_id: str
    ) -> Dict[str, Any]:
        """
        Resolves implicit inputs for a node execution.
        
        Handles:
        1. Context Slicing (Iterative Nodes).
        2. System Context injection.
        
        Returns:
            Dictionary of resolved inputs to merge with command inputs.
        """
        inputs: Dict[str, Any] = {}
        node_state = project.nodes.get(node_id)
        
        if not node_state:
            return inputs

        # --- 1. Iteration Slicing Logic (Map Phase) ---
        if blueprint.iteration and node_state.iteration_index is not None:
            await self._resolve_iteration(project, blueprint, node_state, inputs)

        # --- 2. [NEW] Paper Engine Inputs (Phase 3) ---
        if blueprint.meta.get("executor_engine") == "native_paper_engine":
            await self._resolve_paper_conductor_inputs(project, blueprint, inputs)

        # --- 3. Serial Context Injection ---
        await self._resolve_serial_context(project, blueprint, node_state, inputs)

        return inputs

    async def _resolve_iteration(
        self,
        project: Project,
        blueprint: NodeBlueprint,
        node_state,
        inputs: Dict[str, Any]
    ):
        """Resolves iteration slicing for iterative nodes."""
        driver_id = blueprint.iteration.driver_node_id
        driver_state = project.nodes.get(driver_id)
        
        if driver_state and driver_state.stable_version_id:
            # Load heavy version to get the list
            driver_version = await self.v_repo.get(driver_state.stable_version_id)
            if driver_version and driver_version.selected_output:
                # Extract the specific block
                target_tag = blueprint.iteration.driver_output_tag
                block = driver_version.selected_output.get_block(target_tag)
                
                if block:
                    items = []
                    content = block.content
                    
                    # [FIX] Handle Dual-Anchor Wrapped List (Dict)
                    if isinstance(content, dict):
                        # 优先尝试使用 blueprint 中定义的 tag (例如 "sub_problem_list")
                        # 然后尝试通用的 fallback 键名
                        items = content.get(target_tag) or content.get("sub_problem_list") or []
                    # Fallback for legacy List
                    elif isinstance(content, list):
                        items = content
                    
                    if items:
                        idx = node_state.iteration_index
                        if 0 <= idx < len(items):
                            # Slice and Inject
                            key = blueprint.iteration.context_slice_key
                            sliced_item = items[idx]
                            
                            inputs[key] = sliced_item
                            
                            # Inject Metadata
                            inputs["_iteration"] = {
                                "index": idx,
                                "total": len(items),
                                "driver_id": driver_id
                            }
                            logger.info(f"Sliced input for {node_state.node_id}: {key} = '{str(sliced_item)[:20]}...'")
                        else:
                            logger.warning(f"Index {idx} out of bounds for node {node_state.node_id} (list length: {len(items)})")
                    else:
                        logger.warning(f"Driver output {target_tag} missing or not a list for node {node_state.node_id}")
                else:
                    logger.warning(f"Driver output {target_tag} missing for node {node_state.node_id}")
            else:
                logger.warning(f"Driver node {driver_id} has no stable version output")
        else:
            logger.warning(f"Driver node {driver_id} has no stable version for node {node_state.node_id}")


    async def _resolve_serial_context(
        self,
        project: Project,
        blueprint: NodeBlueprint,
        node_state,
        inputs: Dict[str, Any]
    ):
        """
        Injects serial predecessor context for nodes in serial groups.
        Solves implicit dependencies (e.g., Node 2.2 depends on Node 2.1 output).
        """
        from app.domain.registry import registry
        
        group = registry.get_serial_group(blueprint.id)
        if not group:
            return
        
        my_idx = group.index(blueprint.id)
        if my_idx == 0:
            return  # First in group, no predecessor
        
        pred_base = group[my_idx - 1]
        iter_idx = node_state.iteration_index if node_state.iteration_index is not None else 0
        
        # Predecessor ID assumption (Strict alignment)
        pred_id = f"{pred_base}-{iter_idx}" if blueprint.iteration else pred_base
        
        pred_node = project.nodes.get(pred_id)
        if pred_node and pred_node.stable_version_id:
            ver = await self.v_repo.get(pred_node.stable_version_id)
            if ver and ver.selected_output:
                # Inject as 'previous_output' or 'serial_context'
                inputs["previous_output"] = ver.selected_output.to_context_dict()
                logger.info(f"Injected serial context from {pred_id} to {node_state.node_id}")

    async def _resolve_paper_conductor_inputs(
        self,
        project: Project,
        blueprint: NodeBlueprint,
        inputs: Dict[str, Any]
    ):
        """Injects Outline from Node 3.1."""
        source_id = blueprint.meta.get("blueprint_source", "3.1")
        node = project.nodes.get(source_id)
        if node and node.stable_version_id:
            ver = await self.v_repo.get(node.stable_version_id)
            if ver and ver.selected_output:
                blk = (
                    ver.selected_output.get_block("outline") or
                    ver.selected_output.get_block("paper_blueprint") or
                    ver.selected_output.get_block("json")
                )
                if blk:
                    if isinstance(blk.content, dict):
                        if "outline" in blk.content:
                            inputs["outline"] = blk.content.get("outline", [])
                        elif "structure" in blk.content and isinstance(blk.content.get("structure"), list):
                            titles = []

                            def walk(nodes):
                                for node in nodes:
                                    if isinstance(node, dict) and node.get("title"):
                                        titles.append(str(node.get("title")))
                                    subs = node.get("subsections") if isinstance(node, dict) else None
                                    if isinstance(subs, list):
                                        walk(subs)

                            walk(blk.content.get("structure") or [])
                            inputs["outline"] = titles
                    elif isinstance(blk.content, list):
                        inputs["outline"] = blk.content
