"""
API Routes - Controllers connecting HTTP endpoints to Domain Services.
[REFACTORED] Complete coverage of Project CRUD, Asset Management, and Unified Interactions.
"""
import asyncio
import logging
import urllib.parse  # [NEW] For safe filename encoding
from uuid import UUID
from typing import List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse

from app.core.events import EventBus
from app.core.definitions import NodeStatus, BlockType
from app.domain.registry import registry
from app.domain.payloads import RunNodeCommand, UpdateNodeCommand, CommitNodeCommand

from app.infra.persistence.repositories import ProjectRepository, VersionRepository
from app.infra.asset_manager import AssetManager
from app.infra.gateways.llm import LLMGateway

from app.services.workflow_service import WorkflowService
from app.services.copilot_service import CopilotService
from app.services.view_assembler import ViewAssembler
from app.services.export_service import ExportService
from app.utils.files import guess_mime_type, is_file_type_allowed  # [NEW] For MIME type detection and validation

from app.api.schemas import (
    UpdateProjectRequest, ProjectSummary, ProjectCreatedResponse,  # [FIX] Import new schema
    InteractionRequest, AssetUploadResponse, VersionSummary,
    TimelineResponse, TimelineNodeItem,
    NodeWorkspaceView, NodeDefinitionView, NodeStateView,
    CopilotChatRequest, ChatCompletionRequest,
    ForkNodeRequest, RestoreNodeRequest,
    NodeHistoryResponse, UnifiedHistoryEntry, HistoryArtifact,  # [REFACTORED] Linear history
    ProjectDetailResponse,  # [NEW] Add new schema for project detail
    CopilotSession,  # [NEW] Session schema
    RuntimeConfig  # [BYOK] Runtime configuration
)
from app.domain.unified_io import CopilotStreamChunk
from app.api.deps import (
    get_workflow_service, get_project_repo, get_version_repo,
    get_event_bus, get_asset_manager, get_current_user_id,
    get_copilot_service, get_view_assembler, get_llm_gateway,
    get_runtime_config, get_export_service  # [BYOK] Runtime config dependency
)

router = APIRouter()
logger = logging.getLogger(__name__)


# [NEW] SSE Helper
def format_sse(data: Any, event: Optional[str] = None) -> str:
    """Safely formats data as SSE."""
    import json
    payload = json.dumps(data) if not isinstance(data, str) else data
    msg = f"data: {payload}\n\n"
    if event:
        msg = f"event: {event}\n{msg}"
    return msg


# ==========================================
# 0. [FIX Issue 3] Direct LLM Chat Endpoint
# ==========================================

@router.post("/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    llm: LLMGateway = Depends(get_llm_gateway),
    user_id: str = Depends(get_current_user_id),
    runtime: RuntimeConfig = Depends(get_runtime_config)  # [BYOK]
):
    """
    Standard OpenAI-compatible Chat Completion endpoint.
    Used by 'useLLMStream' hook for direct, non-context-aware interactions.
    """
    async def stream_generator():
        # Convert Pydantic models to dicts for the gateway
        messages_dicts = [m.model_dump() for m in req.messages]
        
        try:
            # Re-use CopilotStreamChunk logic or standard chunks
            async for chunk in llm.stream_chat(
                messages=messages_dicts,
                model_config=None, # Use system default or extract from req if needed
                temperature=req.temperature,
                runtime=runtime  # [BYOK]
            ):
                # Construct OpenAI-compatible chunk
                delta = {}
                if chunk.content:
                    delta["content"] = chunk.content
                if chunk.thought:
                    delta["reasoning_content"] = chunk.thought # DeepSeek standard
                
                openai_chunk = {
                    "id": "chatcmpl-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "finish_reason": chunk.finish_reason
                        }
                    ]
                }
                # [FIX] Use safe formatter
                yield format_sse(openai_chunk)
            
            yield format_sse("[DONE]")
            
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield format_sse({"error": str(e)})

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ==========================================
# 1. Asset Management (Files)
# ==========================================

@router.post("/assets/upload", response_model=AssetUploadResponse, status_code=201)
async def upload_assets(
    files: List[UploadFile] = File(...),
    asset_mgr: AssetManager = Depends(get_asset_manager),
    user_id: str = Depends(get_current_user_id),
):
    """
    [NEW] Upload raw files to CAS.
    Returns the file manifest (Filename -> Hash) to be used in RunNode commands.
    Prohibits images and zip files.
    """
    manifest = {}
    total_size = 0
    
    for file in files:
        # Validate file type
        is_allowed, error_msg = is_file_type_allowed(file.filename)
        if not is_allowed:
            raise HTTPException(status_code=400, detail=error_msg)
        
        try:
            content = await file.read()
            blob_hash = await asset_mgr.save_bytes(content)
            manifest[file.filename] = blob_hash
            total_size += len(content)
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            # Partial success is allowed, or raise error? For now, skip failed
            pass
            
    return AssetUploadResponse(
        manifest=manifest,
        meta={"uploaded_count": len(manifest), "total_size_bytes": total_size}
    )

@router.get("/assets/{blob_hash}")
async def get_asset(
    blob_hash: str,
    filename: Optional[str] = None,  # [FIX] Add optional filename param for MIME inference
    user_id: str = Depends(get_current_user_id),
    asset_mgr: AssetManager = Depends(get_asset_manager)
):
    """
    [CAS Access] Direct access to physical assets by hash.
    Requires valid User Token, but not bound to specific Project permissions.
    """
    if not blob_hash or len(blob_hash) < 6:
        raise HTTPException(404, "Invalid asset hash")
    data = await asset_mgr.get_asset_bytes(blob_hash)
    if not data:
        raise HTTPException(404, "Asset not found")
    
    # [FIX] Dynamic MIME Type Inference
    # Default to octet-stream (download), but try to infer from provided filename query param
    media_type = "application/octet-stream"
    if filename:
        media_type = guess_mime_type(filename)
    
    # [OPTIMIZATION] Add Cache-Control for immutable CAS content
    # CAS content is immutable by definition (hash derived), so we can cache aggressively.
    return Response(
        content=data, 
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )

# [FIX] Issue 1: Implement Project-Context File Download
@router.get("/projects/{project_id}/files/download")
async def download_project_file(
    project_id: UUID,
    path: str,
    user_id: str = Depends(get_current_user_id),
    repo: ProjectRepository = Depends(get_project_repo),
    asset_mgr: AssetManager = Depends(get_asset_manager)
):
    """
    Download file using virtual path (e.g. history/1.1-0/data.csv).
    Resolves virtual path to physical blob hash via Project Assets manifest.
    """
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    # [SECURITY FIX] Check Ownership / Permissions
    # Prevent IDOR (Insecure Direct Object Reference)
    if project.owner_id != user_id:
        # Return 404 to avoid leaking existence of other users' projects
        raise HTTPException(404, "Project not found")

    # 1. Exact Match (Preferred)
    blob_hash = project.assets.get(path)
    
    # 2. Heuristic Match (Fallback)
    if not blob_hash:
        matches = [h for k, h in project.assets.items() if k.endswith(f"/{path}") or k == path]
        if matches:
            blob_hash = matches[-1]
        else:
            raise HTTPException(404, f"File not found: {path}")

    # Stream Content
    data = await asset_mgr.get_asset_bytes(blob_hash)
    if not data:
        raise HTTPException(404, "Physical asset missing (CAS inconsistency)")
    
    # Determine MIME type
    media_type = guess_mime_type(path)

    # [OPTIMIZE] Handle filename encoding for non-ASCII characters (RFC 5987)
    filename = path.split("/")[-1]
    encoded_filename = urllib.parse.quote(filename)
    
    return Response(
        content=data, 
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ==========================================
# 2. Project Management
# ==========================================

# [FIX] Issue 3: Use ProjectCreatedResponse to return assets
@router.post("/projects", response_model=ProjectCreatedResponse, status_code=201)
async def create_project(
    # [FIX] 使用 Form 和 File 替代 JSON Body，解决 422 错误
    name: str = Form(...),
    instruction: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service),
    asset_mgr: AssetManager = Depends(get_asset_manager),
    runtime: RuntimeConfig = Depends(get_runtime_config)  # [BYOK]
):
    """
    创建项目 (支持 multipart/form-data)。
    1. 接收文件流并存入 CAS，生成 manifest。
    2. 创建项目记录。
    3. 如果包含 instruction，自动触发首个节点 (Node 1.1) 的运行。
    """
    # 1. Handle File Uploads (Pre-process)
    initial_assets = {}
    if files:
        for file in files:
            # Validate file type
            is_allowed, error_msg = is_file_type_allowed(file.filename)
            if not is_allowed:
                raise HTTPException(status_code=400, detail=error_msg)
            
            try:
                content = await file.read()
                # 只有非空文件才处理
                if content:
                    blob_hash = await asset_mgr.save_bytes(content)
                    initial_assets[file.filename] = blob_hash
            except Exception as e:
                logger.error(f"Failed to process initial file {file.filename}: {e}")

    # 2. Create Project (Delegate to Service)
    # Service now handles the "Auto-Run" logic if instruction is provided
    project = await ws.create_project(
        name=name, 
        owner_id=user_id, 
        assets=initial_assets, 
        initial_instruction=instruction,
        runtime=runtime  # [BYOK]
    )
    
    return ProjectCreatedResponse(
        id=project.id,
        name=project.name,
        updated_at=project.updated_at,
        assets=project.assets  # [FIX] Ensure assets are returned
    )

@router.get("/projects", response_model=List[ProjectSummary])
async def list_projects(
    user_id: str = Depends(get_current_user_id),
    repo: ProjectRepository = Depends(get_project_repo)
):
    projects = await repo.list_by_owner(user_id)
    return [
        ProjectSummary(id=p.id, name=p.name, updated_at=p.updated_at)
        for p in projects
    ]

@router.patch("/projects/{project_id}", response_model=ProjectSummary)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service)
):
    """[NEW] Update project metadata."""
    try:
        project = await ws.update_project(project_id, request.name, request.assets)
        return ProjectSummary(id=project.id, name=project.name, updated_at=project.updated_at)
    except Exception as e:
        raise HTTPException(404, str(e))

@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service)
):
    """[NEW] Delete project."""
    try:
        await ws.delete_project(project_id)
    except Exception as e:
        raise HTTPException(404, str(e))

@router.get("/projects/{project_id}/assets")
async def get_project_assets(
    project_id: UUID,
    user_id: str = Depends(get_current_user_id),
    repo: ProjectRepository = Depends(get_project_repo)
):
    """[NEW] Get global project asset manifest."""
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    # [SECURITY] Check ownership
    if project.owner_id != user_id:
        raise HTTPException(404, "Project not found")
    return project.assets

@router.get("/projects/{project_id}/export")
async def export_project_zip(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    service: ExportService = Depends(get_export_service),
    p_repo: ProjectRepository = Depends(get_project_repo)
):
    """
    Full Project Export (Streamed ZIP).
    Compresses project state, assets, and logs into a downloadable archive.
    """
    try:
        pid = UUID(project_id)
    except ValueError:
         raise HTTPException(400, "Invalid project ID format")

    project = await p_repo.get(pid)
    
    if not project:
        raise HTTPException(404, "Project not found")
        
    # Security check
    if project.owner_id != user_id:
        raise HTTPException(404, "Project not found")

    try:
        # 1. Initialize the export stream generator
        stream = await service.export_stream(project_id)
        
        # 2. Format filename (RFC 5987 compliant for UTF-8 support)
        # e.g. "My_Project_Export_20231027.zip"
        safe_name = urllib.parse.quote(project.name.replace(" ", "_"))
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        filename = f"{safe_name}_Export_{timestamp}.zip"

        # 3. Return Streaming Response
        return StreamingResponse(
            stream,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"Export failed for project {project_id}: {e}", exc_info=True)
        raise HTTPException(500, "Failed to generate project export.")

# [FIX Issue 2] Add specific project detail endpoint to support GlobalBeacon
@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project_detail(
    project_id: UUID,
    user_id: str = Depends(get_current_user_id),
    repo: ProjectRepository = Depends(get_project_repo)
):
    """
    获取项目详情、拓扑状态及挂起的交互任务。
    This drives the GlobalBeacon (Top Bar) in the frontend.
    """
    project = await repo.get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    
    # [OPTIMIZATION] 逻辑抽取：计算聚合状态
    # 优先查找 REVIEWING (需人工介入)，其次 RUNNING (系统忙)，最后 IDLE
    pending_interaction = None
    active_count = 0
    
    # 按照拓扑顺序排序检查可能更好，但简单遍历足以满足 MVP
    for nid, ns in project.nodes.items():
        # 1. 查找挂起交互 (Priority 1)
        if ns.status == NodeStatus.REVIEWING and not pending_interaction:
            blueprint = registry.get(ns.base_id)
            title = blueprint.title if blueprint else nid
            
            # 构造合成的交互请求对象
            pending_interaction = InteractionRequest(
                action="review_required",
                node_id=nid,
                payload={
                    "title": title,
                    "status": "REVIEWING", 
                    "message": f"Node '{title}' is ready for review.",
                    "requires_action": True
                }
            )
        
        # 2. 统计活跃节点
        if ns.status == NodeStatus.DRAFTING:
            active_count += 1

    # 状态优先级状态机
    if pending_interaction:
        status_summary = "WAITING"
    elif active_count > 0:
        status_summary = "RUNNING"
    else:
        status_summary = "IDLE"

    # 序列化节点状态
    topology = {nid: ns.model_dump(mode='json') for nid, ns in project.nodes.items()}

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        status=status_summary,
        execution_topology=topology,
        pending_interaction=pending_interaction
    )


# ==========================================
# 3. Workflow Views & History
# ==========================================

@router.get("/projects/{project_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_id: UUID,
    user_id: str = Depends(get_current_user_id),
    repo: ProjectRepository = Depends(get_project_repo)
):
    project = await repo.get(project_id)
    if not project or project.owner_id != user_id:
        raise HTTPException(404, "Project not found")
    
    # [FIX] Topological Horizon Calculation
    # Determine the furthest point the user has reached in the linear sequence.
    # We only count nodes that have actively started or finished as "Active".
    max_active_index = -1
    active_statuses = [NodeStatus.DRAFTING, NodeStatus.REVIEWING, NodeStatus.COMMITTED, NodeStatus.FAILED]
    
    for ns in project.nodes.values():
        if ns.status in active_statuses:
            idx = registry.get_global_index(ns.base_id)
            if idx > max_active_index:
                max_active_index = idx
    
    # Visible Horizon = Furthest Active + 1 (Preview the immediate next step)
    # If project is empty (max=-1), horizon=0 (Show first node 1.1)
    visible_horizon_index = max_active_index + 1
    
    items = []
    
    # Build Timeline strictly within Horizon
    for blueprint in registry.get_all():
        bp_index = registry.get_global_index(blueprint.id)
        
        # [Fog of War] Strict Cutoff
        if bp_index > visible_horizon_index:
            break  # Stop processing further nodes
            
        # Dynamic Nodes (Iterative)
        if blueprint.iteration:
             # Find all active instances in project.nodes matching base_id
             instances = [n for n in project.nodes.values() if n.base_id == blueprint.id]
             instances.sort(key=lambda x: x.iteration_index if x.iteration_index is not None else 0)
             
             if instances:
                 for inst in instances:
                     items.append(TimelineNodeItem(
                         id=inst.node_id, 
                         base_id=inst.base_id, 
                         title=f"{blueprint.title} #{inst.iteration_index + 1}",
                         status=inst.status, 
                         phase=blueprint.phase_label, 
                         iteration_index=inst.iteration_index, 
                         updated_at=inst.updated_at
                     ))
             else:
                 # If we are strictly AT this step (it's the horizon), show a placeholder
                 if bp_index <= visible_horizon_index:
                     items.append(TimelineNodeItem(
                         id=f"{blueprint.id}-0",
                         base_id=blueprint.id,
                         title=f"{blueprint.title}",
                         status=NodeStatus.LOCKED,
                         phase=blueprint.phase_label,
                         iteration_index=0,
                         updated_at=None,
                         is_structural_driver=False
                     ))
        else:
             # Static Node
             node_state = project.nodes.get(blueprint.id)
             
             if node_state:
                 status = node_state.status
                 updated_at = node_state.updated_at
             else:
                 # Virtual Placeholder for Horizon Preview
                 # If this node is the horizon, we show it as LOCKED or VOID to indicate "Next"
                 status = NodeStatus.LOCKED
                 if bp_index == visible_horizon_index and max_active_index == -1 and blueprint.id == "1.1":
                     status = NodeStatus.VOID # Special case for very start
                 updated_at = None
             
             items.append(TimelineNodeItem(
                 id=blueprint.id, 
                 base_id=blueprint.id, 
                 title=blueprint.title,
                 status=status, 
                 phase=blueprint.phase_label, 
                 updated_at=updated_at, 
                 is_structural_driver=blueprint.is_structural
             ))
    
    # --- [FIX] Re-sort items to match Execution Topology (Depth-First for Phase 2) ---
    def timeline_sort_key(item: TimelineNodeItem):
        # 1. Get Phase Index
        phase_idx = registry.get_phase_index(item.base_id)
        
        # 2. Get Blueprint Sequence Index (2.1 vs 2.2 vs 2.3)
        bp_seq_idx = registry.get_global_index(item.base_id)
        
        # 3. Get Iteration Index
        iter_idx = item.iteration_index if item.iteration_index is not None else 0
        
        # [Rule Matches TopologyService._calculate_rank]
        # Phase 2 (Modeling, phase_idx=1) is Depth-First: 优先按 Iteration 排序
        if phase_idx == 1:
            return (phase_idx, iter_idx, bp_seq_idx)
        
        # Other Phases are Sequence-First: 优先按 Blueprint 排序
        return (phase_idx, bp_seq_idx, iter_idx)
    
    # Apply the sort
    items.sort(key=timeline_sort_key)
    # --- [FIX END] ---
    
    # Calculate Suggested Next Node
    suggested_node_id = None
    
    # Priority 1: Active Attention Needed
    for item in items:
        if item.status in [NodeStatus.DRAFTING, NodeStatus.REVIEWING, NodeStatus.FAILED]:
            suggested_node_id = item.id
            break
            
    # Priority 2: Ready to Start
    if not suggested_node_id:
        for item in items:
            if item.status == NodeStatus.VOID:
                suggested_node_id = item.id
                break
    
    # Priority 3: Latest visible
    if not suggested_node_id and items:
        suggested_node_id = items[-1].id

    return TimelineResponse(
        project_id=project.id, 
        name=project.name, 
        nodes=items,
        suggested_next_node=suggested_node_id
    )

@router.get("/projects/{project_id}/nodes/{node_id}", response_model=NodeWorkspaceView)
async def get_node_workspace(
    project_id: UUID,
    node_id: str,
    user_id: str = Depends(get_current_user_id),
    p_repo: ProjectRepository = Depends(get_project_repo),
    v_repo: VersionRepository = Depends(get_version_repo),
    assembler: ViewAssembler = Depends(get_view_assembler)
):
    """
    Returns the full UI state for a node (Definition + State + Blocks + Actions).
    Uses ViewAssembler for decoupling.
    """
    project = await p_repo.get(project_id)
    if not project: raise HTTPException(404, "Project not found")

    # Resolve blueprint (handle dynamic IDs like 2.1-0)
    base_id = node_id.split('-')[0] if '-' in node_id else node_id
    blueprint = registry.get(base_id)
    if not blueprint: raise HTTPException(404, "Node definition not found")

    node_state = project.nodes.get(node_id)
    target_version = None
    
    if node_state:
        # Priority: Working > Stable
        target_vid = node_state.working_version_id or node_state.stable_version_id
        if target_vid:
            target_version = await v_repo.get(target_vid)
    
    # Delegate to Assembler
    return assembler.assemble(project, node_id, blueprint, target_version)


@router.get("/projects/{project_id}/nodes/{node_id}/versions", response_model=List[VersionSummary])
async def list_node_versions(
    project_id: UUID,
    node_id: str,
    user_id: str = Depends(get_current_user_id),
    v_repo: VersionRepository = Depends(get_version_repo)
):
    """[NEW] Get history list for time-travel UI."""
    return await v_repo.list_summaries_by_node(project_id, node_id)

@router.get("/projects/{project_id}/nodes/{node_id}/history", response_model=NodeHistoryResponse)
async def get_node_history(
    project_id: UUID,
    node_id: str,
    user_id: str = Depends(get_current_user_id),
    v_repo: VersionRepository = Depends(get_version_repo),
    p_repo: ProjectRepository = Depends(get_project_repo),
    assembler: ViewAssembler = Depends(get_view_assembler)
):
    """
    Returns linear timeline of versions for a node.
    [REFACTORED] Strict Linear Versioning model - no nested HITL structures.
    """
    summaries = await v_repo.list_summaries_by_node(project_id, node_id)
    summaries.sort(key=lambda x: x["created_at"])  # Oldest first
    
    version_ids = [s["id"] for s in summaries]
    full_versions = await v_repo.get_batch(version_ids)
    version_map = {v.id: v for v in full_versions}
    
    project = await p_repo.get(project_id)
    node_state = project.nodes.get(node_id) if project else None
    stable_id = node_state.stable_version_id if node_state else None
    working_id = node_state.working_version_id if node_state else None
    
    timeline = []
    
    # [FIX] Get project and node state for status determination
    project = await p_repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    node_state = project.get_node(node_id)
    stable_id = node_state.stable_version_id if node_state else None
    working_id = node_state.working_version_id if node_state else None
    
    # Get blueprint for ViewAssembler
    base_id = node_id.split('-')[0] if '-' in node_id else node_id
    blueprint = registry.get(base_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    import traceback
    try:
        for idx, s in enumerate(summaries):
            # Resolve model from map
            v_id = s.get("id")
            v = version_map.get(v_id)
            if not v or not v.selected_output:
                logger.warning(f"Version {v_id} not found or has no selected output")
                continue
                
            # 1. Determine Status
            status = "OBSOLETE"
            if v.id == stable_id:
                status = "COMMITTED"
            elif v.id == working_id:
                status = node_state.status.value if node_state else "DRAFTING"
            else:
                if v.selected_output.metadata.get("exit_code", 0) != 0:
                    status = "FAILED"

            # 2. Extract Artifacts (for Timeline Preview)
            v_artifacts = []
            for b in v.selected_output.blocks:
                try:
                    if b.type in [BlockType.DATA, BlockType.FILE]:
                        # [FIX] Use detected MIME type if available, otherwise fallback to BlockType
                        a_type = b.meta.get("mime_type") or str(b.render_type.value if b.render_type else b.type.value)
                        v_artifacts.append(HistoryArtifact(
                            id=b.id,
                            type=a_type,
                            timestamp=v.created_at.timestamp() * 1000,
                            status="ready",
                            summary=b.label
                        ))
                    elif b.type == BlockType.CODE:
                        v_artifacts.append(HistoryArtifact(
                            id=b.id,
                            type="code",
                            timestamp=v.created_at.timestamp() * 1000,
                            status="ready",
                            summary=b.label or "Source Code"
                        ))
                    elif b.type == BlockType.MARKDOWN:
                        is_log = any(t in (b.tags or []) for t in ["logs", "stdout", "stderr", "execution_logs"])
                        if is_log:
                            v_artifacts.append(HistoryArtifact(
                                id=b.id,
                                type="logs",
                                timestamp=v.created_at.timestamp() * 1000,
                                status="ready",
                                summary=b.label or "Execution Logs"
                            ))
                except Exception as artifact_e:
                    logger.warning(f"Failed to extract artifact from block {b.id}: {artifact_e}")

            # 3. Assemble Snapshot Data (Standardized via ViewAssembler)
            try:
                view_state = assembler.assemble(project, node_id, blueprint, v)
                v_data = {
                    "thought": v.selected_output.thought or "",
                    "blocks": [b.to_ui_dict() for b in view_state.state.blocks],
                    "metadata": v.selected_output.metadata
                }
            except Exception as e:
                logger.warning(f"Failed to assemble history view for version {v.id}: {e}")
                v_data = v.selected_output.to_ui_dict()

            # 4. Permissions
            can_rollback = (status == "OBSOLETE" or status == "FAILED")
            
            try:
                entry = UnifiedHistoryEntry(
                    id=v.id,
                    node_id=node_id,
                    version_index=int(s.get("version_index", idx)),
                    timestamp=v.created_at.isoformat(),
                    status=status,
                    trigger=str(v.provenance.get("trigger", "REFINE")),
                    parent_id=v.provenance.get("parent_version_id") if v.provenance.get("parent_version_id") else None,
                    data=v_data,
                    artifacts=v_artifacts,
                    permissions={"can_rollback": can_rollback, "can_delete": True},
                    meta={"intent": v.provenance.get("intent", "refine")}
                )
                timeline.append(entry)
            except Exception as entry_e:
                logger.error(f"Failed to construct UnifiedHistoryEntry for version {v.id}: {entry_e}")
                logger.error(traceback.format_exc())

        return NodeHistoryResponse(timeline=timeline)
    except Exception as global_e:
        logger.error(f"Global error in get_node_history: {global_e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(global_e))


@router.get("/projects/{project_id}/nodes/{node_id}/versions/{version_id}", response_model=NodeWorkspaceView)
async def preview_node_version(
    project_id: UUID,
    node_id: str,
    version_id: UUID,
    user_id: str = Depends(get_current_user_id),
    p_repo: ProjectRepository = Depends(get_project_repo),
    v_repo: VersionRepository = Depends(get_version_repo),
    assembler: ViewAssembler = Depends(get_view_assembler)
):
    """[NEW] Preview a specific historical version (Read-only)."""
    project = await p_repo.get(project_id)
    if not project: raise HTTPException(404, "Project not found")
    
    base_id = node_id.split('-')[0] if '-' in node_id else node_id
    blueprint = registry.get(base_id)
    if not blueprint: raise HTTPException(404, "Blueprint not found")

    version = await v_repo.get(version_id)
    if not version: raise HTTPException(404, "Version not found")

    # Assemble view using this specific version
    return assembler.assemble(project, node_id, blueprint, version)


# ==========================================
# 4. Unified Interaction (Write)
# ==========================================

@router.post("/projects/{project_id}/nodes/{node_id}/interaction", status_code=202)
async def handle_interaction(
    project_id: str,
    node_id: str,
    request: InteractionRequest,
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service),
    runtime: RuntimeConfig = Depends(get_runtime_config)  # [BYOK]
):
    """
    [NEW] Polymorphic endpoint for all UI actions.
    Route all 'submit', 'approve', 'run', 'custom' actions here.
    """
    try:
        # Ensure node_id from path takes precedence (create new request with updated node_id)
        request = request.model_copy(update={"node_id": node_id})
        await ws.handle_interaction(project_id, request, runtime=runtime)  # [BYOK]
        return {"status": "accepted", "action": request.action}
    except Exception as e:
        logger.error(f"Interaction failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# [FIX Issue 6] RPC Routes with Index Support
@router.post("/projects/{project_id}/nodes/{node_id}/fork", status_code=202)
async def fork_node_rpc(
    project_id: str,
    node_id: str,
    request: ForkNodeRequest, # Uses the new schema
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service)
):
    # Logic moved to Service Layer to handle Index->UUID resolution
    # We just delegate params
    target_uuid = request.base_version_id
    if not target_uuid and request.base_version_index is not None:
        target_uuid = await ws._resolve_version_by_index(project_id, node_id, request.base_version_index)
        
    if not target_uuid:
         raise HTTPException(422, "Invalid base_version_id or base_version_index")

    # [FIX] Resolve artifact_id to target_output_index if provided
    target_output_index = request.target_output_index
    if request.artifact_id and target_uuid:
        target_output_index = await ws._resolve_output_index_by_artifact(target_uuid, request.artifact_id)
        if target_output_index is None:
            raise HTTPException(404, f"Artifact {request.artifact_id} not found in version {target_uuid}")

    await ws.fork_node(
        project_id=project_id,
        node_id=node_id,
        base_version_id=target_uuid,
        target_output_index=target_output_index
    )
    return {"status": "forked"}

@router.post("/projects/{project_id}/nodes/{node_id}/restore", status_code=202)
async def restore_node_rpc(
    project_id: str,
    node_id: str,
    request: RestoreNodeRequest,
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service)
):
    target_uuid = request.version_id
    if not target_uuid and request.version_index is not None:
        target_uuid = await ws._resolve_version_by_index(project_id, node_id, request.version_index)
        
    if not target_uuid:
         raise HTTPException(422, "Invalid version_id or version_index")

    await ws.restore_node(
        project_id=project_id,
        node_id=node_id,
        version_id=target_uuid
    )
    return {"status": "restored"}

@router.post("/projects/{project_id}/nodes/{node_id}/reexecute", status_code=202)
async def reexecute_node_rpc(
    project_id: str,
    node_id: str,
    user_id: str = Depends(get_current_user_id),
    ws: WorkflowService = Depends(get_workflow_service)
):
    """RPC Endpoint for Execute-Only (VARL Re-run)."""
    # Create a command with intent="execute_only"
    cmd = RunNodeCommand(
        project_id=project_id,
        node_id=node_id,
        intent="execute_only"
    )
    await ws.run_node(cmd)
    return {"status": "re-executing"}

# ==========================================
# 5. Events & Copilot
# ==========================================

@router.get("/projects/{project_id}/events")
async def stream_events(
    project_id: str,
    bus: EventBus = Depends(get_event_bus)
):
    """Server-Sent Events endpoint."""
    async def event_generator():
        channel = f"project:{project_id}"
        queue = await bus.subscribe(channel)
        try:
            while True:
                msg = await queue.get()
                import json
                yield {
                    "event": msg.get("event", "message"),
                    "data": json.dumps(msg.get("data", {}))
                }
                # Note: asyncio.Queue doesn't have task_done() method (that's queue.Queue)
        except asyncio.CancelledError:
            await bus.unsubscribe(channel, queue)
        except Exception as e:
            logger.error(f"SSE Error: {e}")
            await bus.unsubscribe(channel, queue)

    return EventSourceResponse(event_generator())


# --- Session Management Endpoints ---

@router.get("/projects/{project_id}/sessions", response_model=List[dict])
async def list_copilot_sessions(
    project_id: str,
    copilot: CopilotService = Depends(get_copilot_service),
    user_id: str = Depends(get_current_user_id)
):
    """List all sessions for a project."""
    return await copilot.list_sessions(project_id)

@router.post("/projects/{project_id}/sessions", status_code=201)
async def create_copilot_session(
    project_id: str,
    copilot: CopilotService = Depends(get_copilot_service),
    user_id: str = Depends(get_current_user_id)
):
    """Create a new copilot session."""
    return await copilot.create_session(project_id)

@router.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    copilot: CopilotService = Depends(get_copilot_service),
    user_id: str = Depends(get_current_user_id)
):
    """Get message history for a session."""
    return await copilot.get_history(session_id)

@router.delete("/sessions/{session_id}", status_code=204)
async def delete_copilot_session(
    session_id: str,
    copilot: CopilotService = Depends(get_copilot_service),
    user_id: str = Depends(get_current_user_id)
):
    """Delete (archive) a copilot session."""
    await copilot.delete_session(session_id)

@router.post("/copilot/chat")
async def copilot_chat(
    request: CopilotChatRequest,
    user_id: str = Depends(get_current_user_id),
    copilot: CopilotService = Depends(get_copilot_service),
    runtime: RuntimeConfig = Depends(get_runtime_config)  # [BYOK]
):
    """
    [FIX] Fully Structured SSE Endpoint.
    Returns 'event: token' with JSON payload {content, thought}.
    Matches frontend @microsoft/fetch-event-source expectations.
    """
    msgs = [m.model_dump() for m in request.messages]
    
    async def sse_formatter():
        """
        Adapts internal DTO stream to Server-Sent Events (SSE) protocol.
        """
        try:
            # [FIX] Pass model_config and session_id down to service
            generator = copilot.stream_chat(
                request.project_id, 
                request.current_node_id, 
                msgs,
                model_config=request.llm_config,
                session_id=request.session_id,  # [NEW] Pass session_id
                runtime=runtime  # [BYOK]
            )
            
            async for chunk in generator:
                # 1. Serialize DTO to JSON
                # exclude_unset=True makes payload smaller if thought is empty
                payload = chunk.model_dump_json(exclude_unset=True)
                
                # 2. Format as SSE with custom event name 'token'
                # Frontend expects: if (msg.event === "token")
                yield f"event: token\ndata: {payload}\n\n"
            
            # End of stream (Optional explicit close, though connection close handles it)
            # yield "event: close\ndata: {}\n\n"
            
        except Exception as e:
            logger.error(f"SSE Stream Error: {e}")
            # Send error as data so frontend can display it in chat bubble
            err_payload = CopilotStreamChunk(content=f"\n**Error**: {str(e)}").model_dump_json()
            yield f"event: token\ndata: {err_payload}\n\n"

    return StreamingResponse(
        sse_formatter(),
        media_type="text/event-stream"
    )
