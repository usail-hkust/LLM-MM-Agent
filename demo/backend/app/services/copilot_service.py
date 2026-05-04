"""
Copilot Service - Streaming Chat Engine.

The streaming chat engine that is aware of the project's current state.
"""
import logging
from uuid import UUID
from typing import List, Dict, AsyncGenerator, Optional

from app.domain.registry import registry
from app.infra.persistence.repositories import ProjectRepository, VersionRepository
from app.infra.persistence.copilot_repository import CopilotRepository
from app.infra.gateways.llm import LLMGateway
from app.domain.unified_io import CopilotStreamChunk
from app.api.schemas import ModelConfig, RuntimeConfig
from app.services.context_service import ContextService
from app.core.exceptions import ResourceNotFoundError
from app.core.templates import jinja_env

logger = logging.getLogger(__name__)


class CopilotService:
    """
    [Streaming Service]
    Provides Chat capabilities injected with:
    1. Global Approved History (Stable Pointers)
    2. Current Working Draft (Working Pointer)
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        version_repo: VersionRepository,
        context_service: ContextService,
        llm: LLMGateway,
        copilot_repo: Optional[CopilotRepository] = None
    ):
        self.p_repo = project_repo
        self.v_repo = version_repo
        self.ctx = context_service
        self.llm = llm
        self.repo = copilot_repo or CopilotRepository()  # Default fallback for backward compatibility

    async def create_session(self, project_id: str, title: Optional[str] = None) -> dict:
        """Create a new persisted chat session."""
        session = await self.repo.create_session(project_id, title or "New Chat")
        return {"id": session.id, "title": session.title, "updated_at": session.updated_at}

    async def list_sessions(self, project_id: str) -> List[dict]:
        """List all sessions for a project."""
        sessions = await self.repo.list_sessions(project_id)
        return [{"id": s.id, "title": s.title, "updated_at": s.updated_at} for s in sessions]

    async def get_history(self, session_id: str) -> List[Dict]:
        """Retrieve structured history for frontend."""
        msgs = await self.repo.get_messages(session_id)
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "thought": m.thought,
                "timestamp": m.created_at.timestamp() * 1000
            }
            for m in msgs
        ]

    async def delete_session(self, session_id: str):
        """Delete (archive) a session."""
        await self.repo.delete_session(session_id)

    async def stream_chat(
        self,
        project_id: str,
        current_node_id: Optional[str],
        messages: List[Dict[str, str]],
        model_config: Optional[ModelConfig] = None,
        session_id: Optional[str] = None,
        runtime: Optional[RuntimeConfig] = None  # [BYOK]
    ) -> AsyncGenerator[CopilotStreamChunk, None]:
        """
        Yields structured chunks.
        """
        pid = UUID(project_id)
        project = await self.p_repo.get(pid)
        if not project:
            raise ResourceNotFoundError("Project", project_id)

        # 1. Build Global Context (Upstream Approved)
        # Use current node ID to get everything BEFORE it
        # If node_id is None, implies global project view
        # For global view, use the last node in the registry to get all history
        if current_node_id:
            target_node = current_node_id
        else:
            # Get all history by using a node ID that comes after all nodes
            all_nodes = registry.get_all()
            target_node = all_nodes[-1].id if all_nodes else "999.999"
        
        # [FIX] Unpack 4 values, ignore schemas and dormant assets for now if not used in chat
        history_str, _, _, _ = await self.ctx.build_history(project, target_node)

        # 2. Fetch Current Draft (Working Memory) & Metadata
        draft_str = "(No active draft / User is in read-only mode)"
        node_context_info = "Global Project Overview"

        if current_node_id:
            # A. Resolve Node Title
            title = current_node_id
            blueprint = registry.get(current_node_id)
            # Handle dynamic ID (e.g. 2.1-0) -> Base ID 2.1
            if not blueprint and "-" in current_node_id:
                base_id = current_node_id.rsplit("-", 1)[0]
                blueprint = registry.get(base_id)
            
            if blueprint:
                title = blueprint.title
            
            node_context_info = f"Node: {title} (ID: {current_node_id})"

            # B. Retrieve Draft Content
            node_state = project.nodes.get(current_node_id)
            if node_state and node_state.working_version_id:
                # Fetch heavy version
                ver = await self.v_repo.get(node_state.working_version_id)
                if ver and ver.selected_output:
                    # Enhanced Draft Rendering
                    # Distinguish Code vs Prose to help LLM parsing
                    blocks_text = []
                    for b in ver.selected_output.blocks:
                        if b.type == "CODE":
                            lang = b.meta.get("language", "text")
                            content = str(b.content)
                            blocks_text.append(f"File: {b.label}\n```{lang}\n{content}\n```")
                        elif b.type == "MARKDOWN":
                            content = str(b.content)[:2000]  # Truncate prose if too long
                            blocks_text.append(f"[{b.label}]:\n{content}")
                        elif b.type == "DATA":
                            import json
                            content = json.dumps(b.content, indent=2, default=str)[:1000]
                            blocks_text.append(f"[{b.label}]:\n{content}")
                        else:
                            blocks_text.append(f"[{b.type} - {b.label}]")
                    
                    if blocks_text:
                        draft_str = "\n\n".join(blocks_text)

        # 3. Construct System Prompt with Focus Mechanism
        # Use Jinja template
        try:
            tmpl = jinja_env.get_template("system/copilot_system.j2")
            system_prompt = tmpl.render(
                history_str=history_str,
                node_context_info=node_context_info,
                draft_str=draft_str
            )
        except Exception as e:
            logger.error(f"Copilot template error: {e}")
            # Minimal fallback
            system_prompt = (
                f"You are an AI Copilot.\nContext: {node_context_info}\n"
                f"Draft: {draft_str[:500]}...\nUse history if needed."
            )

        # 4. Build Message Chain (Hybrid Strategy)
        llm_messages = [{"role": "system", "content": system_prompt}]
        
        user_content = messages[-1]["content"] if messages else ""
        
        if session_id:
            # A. Load Persistent History (Exclude current user message to avoid duplication)
            # We fetch DB history FIRST
            db_history = await self.repo.get_messages(session_id, limit=20)
            for msg in db_history:
                llm_messages.append({"role": msg.role, "content": msg.content})
            
            # B. Append Current User Message & Persist It
            if user_content:
                llm_messages.append({"role": "user", "content": user_content})
                # Persist user message
                await self.repo.add_message(
                    session_id, "user", user_content, 
                    meta={"node_id": current_node_id}
                )
        else:
            # Legacy Mode (Stateless)
            llm_messages.extend(messages)

        # 4. Stream & Accumulate
        full_content = ""
        full_thought = ""

        # [BYOK] Pass runtime config to LLM gateway
        async for chunk in self.llm.stream_chat(llm_messages, model_config=model_config, runtime=runtime):
            if chunk.content:
                full_content += chunk.content
            if chunk.thought:
                full_thought += chunk.thought
            yield chunk

        # 5. Persist Assistant Response
        if session_id and (full_content or full_thought):
            await self.repo.add_message(
                session_id, "assistant", full_content,
                thought=full_thought,
                meta={"node_id": current_node_id}
            )
