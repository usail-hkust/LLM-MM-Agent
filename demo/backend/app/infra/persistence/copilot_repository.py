"""
Copilot Repository - Handles persistence for Copilot Sessions and Messages.
"""
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, update, desc
from app.infra.persistence.database import AsyncSessionLocal
from app.infra.persistence.models import CopilotSessionDB, CopilotMessageDB


class CopilotRepository:
    """Repository for managing Copilot sessions and messages."""
    
    async def create_session(self, project_id: str, title: str = "New Chat") -> CopilotSessionDB:
        """Create a new copilot session."""
        session_id = str(uuid4())
        db_obj = CopilotSessionDB(id=session_id, project_id=project_id, title=title)
        async with AsyncSessionLocal() as session:
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
            return db_obj

    async def get_session(self, session_id: str) -> Optional[CopilotSessionDB]:
        """Get a session by ID."""
        async with AsyncSessionLocal() as session:
            return await session.get(CopilotSessionDB, session_id)

    async def list_sessions(self, project_id: str) -> List[CopilotSessionDB]:
        """List all non-archived sessions for a project, ordered by updated_at desc."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CopilotSessionDB)
                .where(CopilotSessionDB.project_id == project_id)
                .where(CopilotSessionDB.is_archived == False)
                .order_by(desc(CopilotSessionDB.updated_at))
            )
            return result.scalars().all()

    async def delete_session(self, session_id: str):
        """Soft delete a session by setting is_archived=True."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(CopilotSessionDB)
                .where(CopilotSessionDB.id == session_id)
                .values(is_archived=True)
            )
            await session.commit()

    async def update_session_title(self, session_id: str, title: str):
        """Update session title and updated_at timestamp."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(CopilotSessionDB)
                .where(CopilotSessionDB.id == session_id)
                .values(title=title, updated_at=datetime.utcnow())
            )
            await session.commit()

    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        thought: Optional[str] = None, 
        meta: Optional[dict] = None
    ) -> CopilotMessageDB:
        """Add a message to a session and update session timestamp."""
        msg_id = str(uuid4())
        msg = CopilotMessageDB(
            id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            thought=thought,
            meta=meta or {}
        )
        async with AsyncSessionLocal() as session:
            session.add(msg)
            # Update session timestamp
            await session.execute(
                update(CopilotSessionDB)
                .where(CopilotSessionDB.id == session_id)
                .values(updated_at=datetime.utcnow())
            )
            await session.commit()
            await session.refresh(msg)
            return msg

    async def get_messages(self, session_id: str, limit: int = 50) -> List[CopilotMessageDB]:
        """Get messages for a session, ordered by created_at ascending."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CopilotMessageDB)
                .where(CopilotMessageDB.session_id == session_id)
                .order_by(CopilotMessageDB.created_at.asc())
                .limit(limit)
            )
            return result.scalars().all()
