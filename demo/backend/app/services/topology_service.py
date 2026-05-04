"""
Topology Service - Linear Navigator.

Responsible for:
1. Flattening the DAG into a strict linear sequence (Total Ordering).
2. Calculating the next node in the pipeline.
3. Eagerly expanding dynamic nodes (Loop Unrolling) & Pruning orphans.
"""
import logging
from typing import List, Optional, Tuple

from uuid import UUID
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.definitions import NodeStatus
from app.core.config import settings
from app.domain.models import Project, NodeState, NodeVersion
from app.domain.registry import registry
from app.domain.events import TimelineUpdateEvent
from app.core.events import EventBus
from app.infra.persistence.models import NodeStateDB


logger = logging.getLogger(__name__)


class TopologyService:
    """
    Sequence Navigator: Manages the strictly ordered execution queue.
    """

    def __init__(self, event_bus: EventBus, redis_client: Optional[Redis] = None):
        self.bus = event_bus
        self.redis_client = redis_client
    
    def _get_cache_key(self, project_id: str) -> str:
        """Get Redis cache key for topology data."""
        return f"{settings.REDIS_PREFIX}:cache:topology:{project_id}"
    
    async def invalidate_cache(self, project_id: str):
        """
        Invalidate topology cache for a project.
        Called after topology changes (expansion, pruning).
        """
        if not self.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(project_id)
            await self.redis_client.delete(cache_key)
            logger.debug(f"Invalidated topology cache for project {project_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate topology cache: {e}")

    def get_linear_successor(self, project: Project, current_node_id: str) -> Optional[str]:
        """
        [Core Algorithm] Calculates the next node in the strict linear pipeline.
        Strategy: 
        1. First check project.nodes for existing successors (ranked order)
        2. If none found, fallback to Registry lookup for next blueprint
        3. Handle both static transitions (1.1 -> 1.2) and iterative nodes (2.1-0 -> 2.1-1 or 2.2-0)
        """
        # Extract base_id and iteration from current_node_id
        base_id = current_node_id.split('-')[0] if '-' in current_node_id else current_node_id
        current_iter = int(current_node_id.split('-')[1]) if '-' in current_node_id else None
        
        # Get current node state to determine its rank
        current_node = project.nodes.get(current_node_id)
        if not current_node:
            # If current node doesn't exist, we can't determine successor
            return None
        
        current_rank = self._calculate_rank(current_node)
        
        # 1. First, check project.nodes for existing successors with higher rank
        ranked_nodes = []
        for ns in project.nodes.values():
            rank = self._calculate_rank(ns)
            ranked_nodes.append((rank, ns.node_id))
        
        # Sort by Rank (Ascending)
        ranked_nodes.sort(key=lambda x: x[0])
        
        # Linear Search for successor in existing nodes
        for i, (rank, nid) in enumerate(ranked_nodes):
            if nid == current_node_id:
                if i + 1 < len(ranked_nodes):
                    next_rank, next_nid = ranked_nodes[i+1]
                    # Verify next node has strictly higher rank
                    if next_rank > current_rank:
                        return next_nid
                break
        
        # 2. No successor found in project.nodes - fallback to Registry lookup
        current_bp = registry.get(base_id)
        if not current_bp:
            logger.warning(f"Blueprint {base_id} not found in registry")
            return None
        
        current_bp_index = registry.get_global_index(base_id)
        current_phase_idx = registry.get_phase_index(base_id)
        
        # Get all blueprints in sequence order
        all_blueprints = registry.get_all()
        
        # Find the next blueprint in the registry sequence
        next_bp = None
        for bp in all_blueprints:
            bp_index = registry.get_global_index(bp.id)
            bp_phase_idx = registry.get_phase_index(bp.id)
            
            # Check if this blueprint comes after current one
            if bp_phase_idx == current_phase_idx:
                # Same phase: compare by blueprint index
                if bp_index > current_bp_index:
                    next_bp = bp
                    break
            elif bp_phase_idx > current_phase_idx:
                # Next phase: this is the successor
                next_bp = bp
                break
        
        if not next_bp:
            # End of pipeline
            return None
        
        # 3. Determine the next node ID based on blueprint type
        next_base_id = next_bp.id
        
        # Check if next blueprint is iterative (depends on a driver)
        if next_bp.iteration:
            # Iterative node: check if iterations have been created by expand_topology
            driver_id = next_bp.iteration.driver_node_id
            
            # Check if driver has been committed
            driver_node = None
            for nid, ns in project.nodes.items():
                if ns.base_id == driver_id and ns.status == NodeStatus.COMMITTED:
                    driver_node = ns
                    break
            
            if not driver_node:
                # Driver not committed yet - can't determine iteration count
                # Return None to wait for driver
                logger.info(f"Pipeline halt: Iterative node {next_base_id} requires committed driver {driver_id}")
                return None
            
            # Driver is committed - check if iterations exist
            existing_iters = []
            for nid, ns in project.nodes.items():
                if ns.base_id == next_base_id and ns.iteration_index is not None:
                    existing_iters.append(ns.iteration_index)
            
            if not existing_iters:
                # No iterations exist - driver didn't produce output (empty loop)
                logger.info(f"Pipeline halt: Iterative node {next_base_id} requires driver {driver_id}, but no iterations exist (empty loop)")
                return None
            
            # Iterations exist - determine which one to return based on current context
            if current_iter is not None:
                # Current node is iterative - determine next based on ranking
                next_bp_index = registry.get_global_index(next_base_id)
                if current_phase_idx == 1:  # Phase 2 (Modeling) - depth-first
                    # Depth-first: 2.1-0 -> 2.2-0 -> 2.3-0 -> 2.1-1
                    if next_bp_index > current_bp_index:
                        # Same iteration, next blueprint
                        return f"{next_base_id}-{current_iter}"
                    else:
                        # Next iteration of first blueprint in group
                        next_iter = min(existing_iters) if existing_iters else 0
                        # Find the first iteration >= current_iter + 1
                        for iter_idx in sorted(existing_iters):
                            if iter_idx > current_iter:
                                return f"{next_base_id}-{iter_idx}"
                        # All iterations are <= current_iter, so we're done with this phase
                        return None
                else:
                    # Standard ordering: next blueprint, iteration 0
                    return f"{next_base_id}-0"
            else:
                # Current is static, next is iterative - return first iteration (iteration 0)
                return f"{next_base_id}-0"
        else:
            # Static node: return base_id directly (WorkflowService will create it if needed)
            return next_base_id

    def _calculate_rank(self, node: NodeState) -> Tuple[int, int, int]:
        """
        Calculates the Linear Sort Rank: (PhaseIndex, MajorKey, MinorKey).
        
        Logic:
        - Phase 2 (Modeling Loop): Depth-First Execution.
          Order: Iteration 0 -> Iteration 1.
          Rank = (Phase, Iteration, BlueprintSequence)
          
        - Phase 1 & 3 (Standard): Sequence-First Execution.
          Order: Step 1 -> Step 2 -> [Step 2.1, 2.2] -> Step 3.
          Rank = (Phase, BlueprintSequence, Iteration)
        """
        # 1. Phase Index (0=Analysis, 1=Modeling, 2=Reporting)
        phase_idx = registry.get_phase_index(node.base_id)
        
        # 2. Static Blueprint Order
        bp_index = registry.get_global_index(node.base_id)
        
        # 3. Dynamic Iteration Order
        iter_idx = node.iteration_index if node.iteration_index is not None else 0
        
        # [Linearization Rules]
        # Phase 2 (Index 1) is the "Modeling Loop". 
        # We want Depth-First: 2.1-0 -> 2.2-0 -> 2.1-1
        if phase_idx == 1: 
            # Rank = (Phase, Iteration, StepOrder)
            return (phase_idx, iter_idx, bp_index)
        else:
            # Standard: 3.1 -> 3.2-0 -> 3.2-1 -> 3.3
            # Rank = (Phase, StepOrder, Iteration)
            return (phase_idx, bp_index, iter_idx)

    async def expand_topology(self, project: Project, driver_node_id: str, count: int, session: AsyncSession) -> List[str]:
        """
        [Eager Expansion & Pruning]
        Triggered on Commit. 
        1. Creates downstream placeholders (LOCKED) if count increases.
        2. DELETEs downstream nodes if count decreases (Pruning).
        """
        driver_state = project.nodes.get(driver_node_id)
        if not driver_state: 
            return []
        
        dependents = registry.get_dependents(driver_state.base_id)
        if not dependents:
            return []

        logger.info(f"Syncing topology for driver {driver_node_id}: Target {count} items")
        
        affected_ids = []
        
        for bp in dependents:
            # A. Expansion (Create Missing)
            for i in range(count):
                node_id = f"{bp.id}-{i}"
                if node_id not in project.nodes:
                    # Create placeholder in LOCKED state
                    ns = NodeState(
                        node_id=node_id,
                        base_id=bp.id,
                        iteration_index=i,
                        status=NodeStatus.LOCKED 
                    )
                    project.nodes[node_id] = ns
                    affected_ids.append(node_id)
                    logger.debug(f"Expanded topology: {node_id}")

            # B. Pruning (Hard Delete Excess)
            # Identify orphans in memory
            orphans = []
            for nid, ns in project.nodes.items():
                if ns.base_id == bp.id:
                    idx = ns.iteration_index if ns.iteration_index is not None else 0
                    if idx >= count:
                        orphans.append(nid)
            
            for nid in orphans:
                logger.info(f"Pruning orphan node: {nid}")
                # 1. Remove from Memory
                del project.nodes[nid]
                
                # 2. Remove from DB (Hard Delete)
                await session.execute(
                    delete(NodeStateDB)
                    .where(NodeStateDB.project_id == str(project.id))
                    .where(NodeStateDB.node_id == nid)
                )
                affected_ids.append(nid)

        if affected_ids:
            await self._emit_timeline_update(str(project.id))
            # Invalidate cache after topology changes
            await self.invalidate_cache(str(project.id))
            
        return affected_ids

    def check_phase_lock(self, project: Project, node_id: str) -> bool:
        """
        Returns True if the node is LOCKED because the previous Phase is strictly active.
        Rule: Phase N cannot start until Phase N-1 is fully settled (All nodes COMMITTED or VOID).
        """
        # 1. Determine Current Phase
        try:
            current_phase = int(node_id.split('.')[0])
        except ValueError:
            return False # Non-standard ID, skip check
            
        if current_phase <= 1:
            return False
            
        prev_phase = current_phase - 1
        prefix = f"{prev_phase}."
        
        # 2. Check all nodes in Previous Phase
        # [CRITICAL FIX] VOID must be treated as active because it represents "pending tasks"
        # If any node in the previous phase is 'Active' (including VOID), we lock the current phase.
        # We allow COMMITTED (done) to proceed.
        
        active_statuses = [NodeStatus.LOCKED, NodeStatus.DRAFTING, NodeStatus.REVIEWING, NodeStatus.FAILED, NodeStatus.VOID]
        
        for nid, node_state in project.nodes.items():
            # Check base_id to see if it belongs to prev phase
            if node_state.base_id.startswith(prefix):
                if node_state.status in active_statuses:
                    logger.warning(f"Phase Lock: Node {node_id} (Phase {current_phase}) waiting for {nid} (Status: {node_state.status})")
                    return True
                    
        return False

    def check_structural_lock(self, project: Project, node_id: str) -> bool:
        """
        Returns True if the node is LOCKED (cannot run) because dependent downstream nodes are active.
        
        Args:
            project: The project containing the nodes
            node_id: The base_id of the node to check (e.g., "1.2")
            
        Returns:
            True if locked (cannot re-run), False if unlocked
        """
        # 1. Identify if node is structural
        blueprint = registry.get(node_id)
        if not blueprint or not blueprint.is_structural:
            return False

        # 2. Find dependents (blueprints that depend on this node as a driver)
        dependents = [
            bp for bp in registry.get_all()
            if bp.iteration and bp.iteration.driver_node_id == node_id
        ]

        if not dependents:
            return False

        # 3. Check status of dependents
        for dep_bp in dependents:
            # Check all instances of this blueprint
            for key, node_state in project.nodes.items():
                if node_state.base_id == dep_bp.id:
                    # If any downstream node has data (is not VOID), we lock the parent
                    if node_state.status != NodeStatus.VOID:
                        logger.warning(f"Structural Lock: {node_id} locked by active dependent {key} (status: {node_state.status})")
                        return True
        
        return False

    def is_node_runnable(self, project: Project, node_id: str) -> bool:
        """
        [NEW] Unified Pre-flight Check.
        
        Determines if a node is eligible for execution by checking all lock types.
        Used by CLI and UI to filter actionable nodes.
        
        Args:
            project: The project containing the nodes
            node_id: The effective node ID to check (e.g., "1.1" or "2.1-0")
            
        Returns:
            True if node can be executed, False otherwise
        """
        node_state = project.nodes.get(node_id)
        if not node_state:
            return False
            
        # 1. Status Check
        # Nodes that are already running, failed, or committed (without explicit re-run intent) shouldn't be auto-scheduled.
        # Note: CLI logic might allow re-running COMMITTED, but generally we look for VOID.
        # FAILED nodes are blocked until manual reset/retry.
        if node_state.status in [NodeStatus.LOCKED, NodeStatus.DRAFTING, NodeStatus.FAILED]:
            return False

        # 2. Structural Lock Check (Downstream dependencies active)
        if self.check_structural_lock(project, node_state.base_id):
            return False

        # 3. Phase Lock Check (Previous phase incomplete)
        if self.check_phase_lock(project, node_id):
            return False
            
        # 4. Serial Lock Check (Managed via Status=LOCKED, covered by step 1)
        # But for robustness, we can ensure we don't run things marked LOCKED
        
        return True

    async def _emit_timeline_update(self, project_id: str):
        channel = f"project:{project_id}"
        event = TimelineUpdateEvent(project_id=project_id)
        await self.bus.publish(channel, event.event, event.data)
