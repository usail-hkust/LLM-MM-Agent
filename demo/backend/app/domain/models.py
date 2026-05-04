"""
Domain Models - Core Entities.
"""
import re
from datetime import datetime
from typing import Dict, Optional, List, Any, Set
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.core.definitions import NodeStatus
from app.domain.unified_io import NodeOutput


class AssetLedgerEntry(BaseModel):
    """
    Single record in the asset ledger.
    Tracks the stable filename assigned to a virtual path.
    """
    target_handle: str  # e.g., "fig_01_heatmap.png"
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    is_archived: bool = False  # Tombstone flag: ID is reserved but currently unused


class AssetLedger(BaseModel):
    """
    Stateful record of Asset ID assignments.
    Prevents ID Drift by persisting mapping: Virtual Path -> Stable Filename.
    """
    next_sequence: int = 1
    # Mapping: Source Virtual Path (e.g. history/1.1/plot.png) -> Ledger Entry
    mappings: Dict[str, AssetLedgerEntry] = Field(default_factory=dict)

    def resolve_or_assign(self, virtual_path: str, extension: str, raw_name: str = "") -> str:
        """
        Lookup-or-Assign Logic:
        1. If exists, return stable handle (Revive if archived).
        2. If new, assign next sequential ID.
        """
        # 1. Lookup
        if virtual_path in self.mappings:
            entry = self.mappings[virtual_path]
            # Revive archived entry to maintain history stability
            if entry.is_archived:
                entry.is_archived = False
            return entry.target_handle

        # 2. Assign New
        seq = self.next_sequence
        self.next_sequence += 1

        if not raw_name:
            raw_name = virtual_path.split("/")[-1].rsplit(".", 1)[0]

        # Sanitize raw_name for human readability
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", raw_name)[:40]

        # Prefix Logic: Images get 'fig_', others get 'asset_'
        # This aligns with LaTeX/Paper Engine conventions
        prefix = "fig" if extension.lower() in [".png", ".jpg", ".jpeg", ".svg", ".pdf", ".eps"] else "asset"
        target_handle = f"{prefix}_{seq:02d}_{safe_name}{extension}"

        self.mappings[virtual_path] = AssetLedgerEntry(target_handle=target_handle)
        return target_handle

    def mark_missing_as_archived(self, current_paths: Set[str]):
        """
        Tombstone Mechanism:
        Mark entries not in the current manifest as archived instead of deleting them.
        This prevents ID reuse and maintains semantic consistency for old references.
        """
        for v_path, entry in self.mappings.items():
            if v_path not in current_paths:
                entry.is_archived = True


class NodeState(BaseModel):
    node_id: str
    base_id: Optional[str] = None
    iteration_index: Optional[int] = None
    status: NodeStatus = NodeStatus.VOID
    stable_version_id: Optional[UUID] = None
    working_version_id: Optional[UUID] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @model_validator(mode='after')
    def _set_base_id_default(self):
        if self.base_id is None:
            if "-" in self.node_id:
                parts = self.node_id.rsplit("-", 1)
                if len(parts) == 2:
                    self.base_id = parts[0]
                    if self.iteration_index is None:
                        try:
                            self.iteration_index = int(parts[1])
                        except ValueError:
                            self.base_id = self.node_id
                            self.iteration_index = None
                else:
                    self.base_id = self.node_id
                    if self.iteration_index is None:
                        self.iteration_index = None
            else:
                self.base_id = self.node_id
                if self.iteration_index is None:
                    self.iteration_index = None
        return self


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    owner_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    nodes: Dict[str, NodeState] = Field(default_factory=dict)
    
    # [FIX] Global Assets (Virtual File Manifest) to solve data loss
    assets: Dict[str, str] = Field(default_factory=dict)
    
    # [NEW] Asset Ledger for ID Persistence
    asset_ledger: AssetLedger = Field(default_factory=AssetLedger)

    def get_node(self, node_id: str) -> NodeState:
        """Safe accessor that initializes node state if missing."""
        if node_id not in self.nodes:
            # [FIX Issue 5] Graceful fallback for Dynamic Nodes
            # Return a virtual VOID state instead of crashing if topology isn't synced yet
            base_id = node_id
            iter_idx = None
            if "-" in node_id:
                parts = node_id.rsplit("-", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    base_id = parts[0]
                    iter_idx = int(parts[1])
            
            self.nodes[node_id] = NodeState(
                node_id=node_id,
                base_id=base_id,
                iteration_index=iter_idx,
                status=NodeStatus.VOID
            )
        return self.nodes[node_id]


class NodeVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    node_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    outputs: List[NodeOutput] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @property
    def selected_output(self) -> Optional[NodeOutput]:
        if not self.outputs:
            return None
        for out in self.outputs:
            if out.is_selected:
                return out
        return self.outputs[-1]
