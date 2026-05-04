"""
API Schemas - Request/Response DTOs.

Defines the structure of JSON bodies for Requests and Responses.
"""
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator

from app.core.definitions import NodeStatus, RenderType, NodeType, BlockType, LayoutMode
from app.domain.blueprints import UXConfig
from app.domain.unified_io import ContentBlock, RenderAction

# --- [NEW] Auth Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    invite_code: Optional[str] = None
    terms_agreed: bool

    @field_validator("terms_agreed")
    @classmethod
    def must_agree(cls, v):
        if not v:
            raise ValueError("You must agree to the terms.")
        return v

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool

# --- [NEW] Runtime Configuration (BYOK) ---
class RuntimeConfig(BaseModel):
    """
    Per-request configuration extracted from Headers.
    Carries BYOK credentials to the infrastructure layer.
    """
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_name: Optional[str] = None
    e2b_api_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Shared Models ---

class ProjectSummary(BaseModel):
    id: UUID
    name: str
    updated_at: datetime

# [FIX] Issue 3: New Schema for Project Creation Response
class ProjectCreatedResponse(ProjectSummary):
    """
    Extended response for project creation that includes the initial asset manifest.
    Ensures frontend has immediate access to file hashes after upload.
    """
    assets: Dict[str, str] = Field(default_factory=dict, description="Global asset manifest (Virtual Path -> Blob Hash)")

class AssetUploadResponse(BaseModel):
    """[NEW] Response for file upload."""
    manifest: Dict[str, str] = Field(description="Map of Filename -> BlobHash")
    meta: Dict[str, Any]

class VersionSummary(BaseModel):
    """[NEW] Lightweight version info for history list."""
    id: UUID
    created_at: datetime
    trigger: str
    intent: str
    meta: Dict[str, Any]

class ChatMessage(BaseModel):
    role: str
    content: str

# [NEW] Dynamic LLM Configuration from Client
class ModelConfig(BaseModel):
    modelName: Optional[str] = None
    baseUrl: Optional[str] = None
    apiKey: Optional[str] = None
    temperature: Optional[float] = 0.7

# [FIX Issue 3] Standard OpenAI Chat Request for direct pass-through
class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o"
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 0.7

# --- Requests (Write) ---

class CreateProjectRequest(BaseModel):
    name: str
    # Optional initial instructions can be handled via a run command later, 
    # but strictly creating a project is just metadata.

class UpdateProjectRequest(BaseModel):
    """[NEW] Project update payload."""
    name: Optional[str] = None
    assets: Optional[Dict[str, str]] = None

class RunNodeRequest(BaseModel):
    """
    Triggers node execution.
    Supports Unified Interaction Loop via `intent`.
    """
    instruction: Optional[str] = None
    # Dynamic inputs for the template (e.g. { "topic": "AI" })
    inputs: Dict[str, Any] = {}
    
    # [Unified Interaction]
    # "generate" (Default): Create fresh content.
    # "critique": Analyze current draft.
    # "refine": Fix current draft based on feedback.
    # "execute_only": Skip LLM, just run code (VARL).
    intent: str = "generate"
    
    # [SCA Configuration]
    # e.g., { "num_samples": 3, "temperature": 0.7 }
    config: Dict[str, Any] = {}

class UpdateNodeRequest(BaseModel):
    # If selecting a candidate from a batch
    selected_output_id: Optional[str] = None
    
    # If manually editing a block
    target_block_id: Optional[str] = None
    manual_content: Optional[str] = None

class InteractionRequest(BaseModel):
    """
    Universal Action Payload.
    [FIX] Renamed 'data' to 'payload' to match frontend contract.
    [FIX] Made node_id Optional to solve 422 Error. 
          It is extracted from the URL path by the route handler.
    """
    action: str  # e.g., "run_node", "submit_approval", "save_draft"
    
    # Context
    # 修复前: node_id: str
    node_id: Optional[str] = None  # <--- 修复点：改为 Optional，允许 Body 中不传
    
    # Dynamic payload
    payload: Dict[str, Any] = Field(default_factory=dict)

class CopilotChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allow access by both field name and alias
    
    project_id: str
    current_node_id: Optional[str] = None  # If null, chat is global
    messages: List[ChatMessage]
    # [FIX] Use 'llm_config' as Python field name (model_config is reserved in Pydantic v2)
    # but keep 'model_config' as JSON alias for frontend compatibility
    llm_config: Optional[ModelConfig] = Field(default=None, alias="model_config")
    session_id: Optional[str] = None  # [NEW] Session ID for persistence

# --- Fork / Branching Requests ---

class ForkNodeRequest(BaseModel):
    """
    [FIX] Support both UUID (strict) and Index (UI-friendly).
    """
    base_version_id: Optional[UUID] = None
    base_version_index: Optional[int] = None
    # Optional: Pick a specific output from the base version (for SCA selection branching)
    # Uses index for simplicity in this version, matching UpdateNodeRequest pattern
    target_output_index: Optional[int] = None 
    # [FIX] Support forking from a specific artifact ID (frontend convenience)
    artifact_id: Optional[str] = None
    
    # "review" (Default: just create draft), "run" (create draft and trigger re-run)
    intent: str = "review"

class RestoreNodeRequest(BaseModel):
    """
    [FIX] Support both UUID (strict) and Index (UI-friendly).
    """
    version_id: Optional[UUID] = None
    version_index: Optional[int] = None
    # If True, delete downstream data? (Usually False, downstream nodes remain unchanged in non-destructive mode)
    hard_reset: bool = False

# --- Responses (Read) ---

class TimelineNodeItem(BaseModel):
    """Summary of a node for the sidebar navigation."""
    id: str             # "2.1-0" (effective ID)
    base_id: str        # "2.1" (blueprint ID)
    title: str          # "Model Design" or "Model Design #1"
    status: NodeStatus
    
    # [NEW] Phase Label for grouping (e.g., "Phase 1: Analysis")
    phase: str 
    
    # New Hierarchy Helpers
    iteration_index: Optional[int] = None  # Index in the driver list (if iterative)
    is_structural_driver: bool = False  # If True, this node drives downstream topology
    
    updated_at: Optional[datetime] = None

class TimelineResponse(BaseModel):
    project_id: UUID
    name: str
    nodes: List[TimelineNodeItem]
    
    # [NEW] Explicit guidance for frontend router
    # Tells the UI which node to select immediately after loading
    suggested_next_node: Optional[str] = None

class NodeDefinitionView(BaseModel):
    """Static part of the node view."""
    id: str
    title: str
    type: NodeType
    ux: UXConfig

class NodeStateView(BaseModel):
    """
    Rich View Model.
    Contains the blocks (with injected actions) and the layout directive.
    """
    status: NodeStatus
    
    # The effective layout to use (calculated by ViewAssembler)
    layout_mode: LayoutMode
    
    # The payload
    blocks: List[ContentBlock] = []
    
    # Metadata
    metadata: Dict[str, Any] = {}
    
    # Global flags
    is_read_only: bool = False
    active_version_id: Optional[UUID] = None
    
    # [NEW] Global Control Plane
    # Actions that apply to the workspace, not specific blocks (e.g., Approve, Reject)
    global_actions: List[RenderAction] = []

class NodeWorkspaceView(BaseModel):
    """Composite view for the main workspace."""
    definition: NodeDefinitionView
    state: NodeStateView

# --- [REFACTORED] Linear History Models ---

class HistoryArtifact(BaseModel):
    id: str
    type: str
    timestamp: float
    status: str
    data: Optional[Any] = None
    summary: Optional[str] = None

class UnifiedHistoryEntry(BaseModel):
    """
    Atomic History Snapshot.
    Replaces hierarchical rounds with a flat linked list structure.
    """
    id: UUID
    node_id: str
    version_index: int
    timestamp: str
    
    # Linear State
    status: str     # e.g. COMMITTED, OBSOLETE, REJECTED
    trigger: str    # e.g. INITIAL_RUN, REFINE, SELECT
    parent_id: Optional[UUID] = None
    
    # Payload
    data: Optional[Dict[str, Any]] = None
    artifacts: List[HistoryArtifact] = []
    permissions: Dict[str, bool] = {}
    meta: Dict[str, Any] = {}

class NodeHistoryResponse(BaseModel):
    timeline: List[UnifiedHistoryEntry]

# [OPTIMIZED] 新增 ProjectDetailResponse 定义
class ProjectDetailResponse(BaseModel):
    """
    聚合视图响应，用于前端 GlobalBeacon 和 Header 状态展示。
    """
    id: UUID
    name: str
    status: str  # "RUNNING" | "WAITING" | "IDLE" | "ERROR"
    execution_topology: Dict[str, Any]  # 完整的节点状态树 NodeState
    pending_interaction: Optional[InteractionRequest] = None  # 当前需要用户处理的交互


class CopilotSession(BaseModel):
    """Session metadata for Copilot chat."""
    id: str
    title: str
    updated_at: datetime
