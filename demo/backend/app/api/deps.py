"""
Dependency Injection - Wires up the application graph.

This is where "Explicit Dependencies" are realized.
"""
import logging
from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

from app.core.config import settings
from app.core.events import EventBus
from app.api.schemas import RuntimeConfig
from app.infra.persistence.redis import get_redis_client

# Infrastructure
from app.infra.persistence.repositories import ProjectRepository, VersionRepository, AuthRepository
from app.infra.persistence.copilot_repository import CopilotRepository
from app.infra.asset_manager import AssetManager
from app.infra.gateways.llm import LLMGateway
from app.infra.gateways.sandbox import SandboxGateway

# Services
from app.services.context_service import ContextService
from app.services.prompt_factory import PromptFactory
from app.services.node_processor import NodeProcessor
from app.services.workflow_service import WorkflowService
from app.services.copilot_service import CopilotService
from app.services.view_assembler import ViewAssembler
from app.services.topology_service import TopologyService
from app.services.input_resolver import InputResolver
from app.paper_engine import PaperEngineManager
from app.services.ingestion_service import IngestionService
from app.services.auth_service import AuthService
from app.services.export_service import ExportService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/token")

logger = logging.getLogger(__name__)

# --- [NEW] BYOK Config Extraction ---

def get_runtime_config(request: Request) -> RuntimeConfig:
    """
    Dependency: Extracts BYOK config from headers.
    NOTE: Backend has NO default API keys - ALL requests must use user-provided keys.
    """
    headers = request.headers
    return RuntimeConfig(
        llm_api_key=headers.get("X-LLM-API-Key"),  # No fallback - user MUST provide
        llm_base_url=headers.get("X-LLM-Base-URL") or None,
        llm_model_name=headers.get("X-LLM-Model") or None,
        e2b_api_key=headers.get("X-E2B-API-Key") or None
    )

# --- Singletons ---

@lru_cache()
def get_event_bus() -> EventBus:
    # Imported from core.events where the instance is created
    from app.core.events import event_bus
    return event_bus

@lru_cache()
def get_asset_manager() -> AssetManager:
    return AssetManager(storage_root=settings.STORAGE_ROOT)

@lru_cache()
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()

@lru_cache()
def get_sandbox_gateway(
    assets: AssetManager = Depends(get_asset_manager)
) -> SandboxGateway:
    return SandboxGateway(assets)

@lru_cache()
def get_prompt_factory() -> PromptFactory:
    return PromptFactory()

# --- Repositories ---
# Repositories are stateless (methods create sessions), so they can be singletons

@lru_cache()
def get_project_repo() -> ProjectRepository:
    return ProjectRepository()

@lru_cache()
def get_version_repo() -> VersionRepository:
    return VersionRepository()

@lru_cache()
def get_copilot_repo() -> CopilotRepository:
    return CopilotRepository()

@lru_cache()
def get_auth_repo() -> AuthRepository:
    return AuthRepository()

# --- Services ---

@lru_cache()
def get_auth_service(
    repo: AuthRepository = Depends(get_auth_repo)
) -> AuthService:
    return AuthService(repo)

@lru_cache()
def get_context_service(
    v_repo: VersionRepository = Depends(get_version_repo)
) -> ContextService:
    return ContextService(v_repo)

@lru_cache()
def get_paper_engine_manager(
    sandbox: SandboxGateway = Depends(get_sandbox_gateway),
    assets: AssetManager = Depends(get_asset_manager),
    llm: LLMGateway = Depends(get_llm_gateway),
    prompts: PromptFactory = Depends(get_prompt_factory),
    event_bus: EventBus = Depends(get_event_bus)
) -> PaperEngineManager:
    return PaperEngineManager(sandbox, assets, llm, prompts, event_bus)

@lru_cache()
def get_node_processor(
    llm: LLMGateway = Depends(get_llm_gateway),
    sandbox: SandboxGateway = Depends(get_sandbox_gateway),
    assets: AssetManager = Depends(get_asset_manager),
    prompts: PromptFactory = Depends(get_prompt_factory),
    paper_manager: PaperEngineManager = Depends(get_paper_engine_manager),
    event_bus: EventBus = Depends(get_event_bus)
) -> NodeProcessor:
    return NodeProcessor(llm, sandbox, assets, prompts, paper_manager, event_bus)

def get_topology_service(
    bus: EventBus = Depends(get_event_bus),
    redis_client = Depends(get_redis_client)
) -> TopologyService:
    return TopologyService(bus, redis_client)

@lru_cache()
def get_input_resolver(
    v_repo: VersionRepository = Depends(get_version_repo)
) -> InputResolver:
    return InputResolver(v_repo)

@lru_cache()
def get_ingestion_service(
    llm: LLMGateway = Depends(get_llm_gateway),
    assets: AssetManager = Depends(get_asset_manager)
) -> IngestionService:
    return IngestionService(llm, assets)

def get_workflow_service(
    p_repo: ProjectRepository = Depends(get_project_repo),
    v_repo: VersionRepository = Depends(get_version_repo),
    processor: NodeProcessor = Depends(get_node_processor),
    ctx_service: ContextService = Depends(get_context_service),
    topo_service: TopologyService = Depends(get_topology_service),
    resolver: InputResolver = Depends(get_input_resolver),
    bus: EventBus = Depends(get_event_bus),
    ingestion: IngestionService = Depends(get_ingestion_service),
    redis_client = Depends(get_redis_client)
) -> WorkflowService:
    return WorkflowService(p_repo, v_repo, processor, ctx_service, topo_service, resolver, bus, ingestion, redis_client)

@lru_cache()
def get_copilot_service(
    p_repo: ProjectRepository = Depends(get_project_repo),
    v_repo: VersionRepository = Depends(get_version_repo),
    ctx_service: ContextService = Depends(get_context_service),
    llm: LLMGateway = Depends(get_llm_gateway),
    copilot_repo: CopilotRepository = Depends(get_copilot_repo)
) -> CopilotService:
    return CopilotService(p_repo, v_repo, ctx_service, llm, copilot_repo)

# --- Add View Assembler ---

@lru_cache()
def get_view_assembler() -> ViewAssembler:
    return ViewAssembler()

@lru_cache()
def get_export_service(
    p_repo: ProjectRepository = Depends(get_project_repo),
    v_repo: VersionRepository = Depends(get_version_repo),
    c_repo: CopilotRepository = Depends(get_copilot_repo),
    assets: AssetManager = Depends(get_asset_manager)
) -> ExportService:
    return ExportService(p_repo, v_repo, c_repo, assets)

# --- Auth ---

async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception
