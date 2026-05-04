"""
Database Models (SQLModel).
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, UniqueConstraint, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class BaseDB(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NodeStateDB(BaseDB, table=True):
    __tablename__ = "node_states"
    __table_args__ = (
        UniqueConstraint("project_id", "node_id", name="uq_project_node"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    node_id: str = Field(index=True)
    base_id: str 
    iteration_index: Optional[int] = None
    status: str
    stable_version_id: Optional[str] = None
    working_version_id: Optional[str] = None


class ProjectDB(BaseDB, table=True):
    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    name: str
    owner_id: str = Field(index=True)
    
    # [FIX] Global Assets Store
    assets: Dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON_TYPE))
    
    # [NEW] Persist the Ledger
    asset_ledger: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON_TYPE))


class NodeVersionDB(BaseDB, table=True):
    __tablename__ = "node_versions"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    node_id: str = Field(index=True)
    outputs: List[Any] = Field(default_factory=list, sa_column=Column(JSON_TYPE))
    provenance: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON_TYPE))


class CopilotSessionDB(BaseDB, table=True):
    __tablename__ = "copilot_sessions"

    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    title: str = Field(default="New Chat")
    is_archived: bool = Field(default=False)


class CopilotMessageDB(BaseDB, table=True):
    __tablename__ = "copilot_messages"

    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    role: str  # "user", "assistant", "system"
    content: str = Field(sa_column=Column(Text))
    thought: Optional[str] = Field(default=None, sa_column=Column(Text))
    meta: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON_TYPE))


class UserDB(BaseDB, table=True):
    __tablename__ = "users"

    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class InvitationCodeDB(BaseDB, table=True):
    __tablename__ = "invitation_codes"

    code: str = Field(primary_key=True)
    is_used: bool = Field(default=False)
    used_by_user_id: Optional[str] = Field(default=None, foreign_key="users.id")
    used_at: Optional[datetime] = Field(default=None)
