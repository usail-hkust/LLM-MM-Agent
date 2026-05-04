"""
Repositories.
"""
import logging
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Project, NodeVersion, NodeState, AssetLedger
from app.core.definitions import NodeStatus
from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError, StateError
from app.infra.persistence.database import AsyncSessionLocal
from app.infra.persistence.models import ProjectDB, NodeVersionDB, NodeStateDB, UserDB, InvitationCodeDB

logger = logging.getLogger(__name__)


class AuthRepository:
    """
    Repository for User and Invitation Code management.
    """
    
    async def get_user_by_email(self, email: str) -> Optional[UserDB]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserDB).where(UserDB.email == email))
            return result.scalar_one_or_none()

    async def create_user_with_invite(self, email: str, hashed_password: str, invite_code: str) -> UserDB:
        """
        Atomically checks invitation code validity, marks it as used, and creates the user.
        Raises ValueError if code is invalid or used.
        """
        from uuid import uuid4
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Lock & Check Invite Code
                # [PostgreSQL] Use FOR UPDATE to prevent concurrent use of the same invite code
                result = await session.execute(
                    select(InvitationCodeDB).where(InvitationCodeDB.code == invite_code).with_for_update()
                )
                code_record = result.scalar_one_or_none()

                if not code_record:
                    raise ResourceNotFoundError("InvitationCode", invite_code)
                
                if code_record.is_used:
                    raise StateError("Invitation code has already been used.")

                # 2. Check if Email Exists (Double Check inside transaction)
                user_check = await session.execute(select(UserDB).where(UserDB.email == email))
                if user_check.scalar_one_or_none():
                    raise StateError("Email already registered.")

                # 3. Create User
                new_user_id = str(uuid4())
                new_user = UserDB(
                    id=new_user_id,
                    email=email,
                    hashed_password=hashed_password,
                    is_active=True
                )
                session.add(new_user)
                # Flush to ensure user is inserted before updating invitation code with foreign key
                await session.flush()

                # 4. Burn Invite Code
                code_record.is_used = True
                code_record.used_by_user_id = new_user_id
                code_record.used_at = datetime.utcnow()
                session.add(code_record)
                
                return new_user

    async def create_user(self, email: str, hashed_password: str) -> UserDB:
        from uuid import uuid4

        async with AsyncSessionLocal() as session:
            async with session.begin():
                user_check = await session.execute(select(UserDB).where(UserDB.email == email))
                if user_check.scalar_one_or_none():
                    raise StateError("Email already registered.")

                new_user = UserDB(
                    id=str(uuid4()),
                    email=email,
                    hashed_password=hashed_password,
                    is_active=True,
                )
                session.add(new_user)
                await session.flush()
                return new_user

    async def generate_invite_codes(self, count: int = 1, prefix: str = "INV") -> List[str]:
        """Admin helper to generate codes."""
        from uuid import uuid4
        codes = []
        async with AsyncSessionLocal() as session:
            async with session.begin():
                for _ in range(count):
                    code_str = f"{prefix}-{str(uuid4())[:8].upper()}"
                    session.add(InvitationCodeDB(code=code_str))
                    codes.append(code_str)
        return codes


class ProjectRepository:
    
    async def get(self, project_id: UUID, session: Optional[AsyncSession] = None) -> Optional[Project]:
        if session:
            return await self._get_impl(session, project_id)
        else:
            async with AsyncSessionLocal() as local_session:
                return await self._get_impl(local_session, project_id)

    async def _get_impl(self, session: AsyncSession, project_id: UUID) -> Optional[Project]:
        result = await session.execute(select(ProjectDB).where(ProjectDB.id == str(project_id)))
        project_row = result.scalar_one_or_none()
        if not project_row:
            return None
            
        ns_result = await session.execute(select(NodeStateDB).where(NodeStateDB.project_id == str(project_id)))
        node_rows = ns_result.scalars().all()
        
        nodes: Dict[str, NodeState] = {}
        for row in node_rows:
            nodes[row.node_id] = NodeState(
                node_id=row.node_id,
                base_id=row.base_id,
                iteration_index=row.iteration_index,
                status=NodeStatus(row.status),
                stable_version_id=UUID(row.stable_version_id) if row.stable_version_id else None,
                working_version_id=UUID(row.working_version_id) if row.working_version_id else None,
                updated_at=row.updated_at
            )

        ledger_data = project_row.asset_ledger or {}
        ledger = AssetLedger(**ledger_data)

        return Project(
            id=UUID(project_row.id),
            name=project_row.name,
            owner_id=project_row.owner_id,
            created_at=project_row.created_at,
            updated_at=project_row.updated_at,
            nodes=nodes,
            assets=project_row.assets or {},
            asset_ledger=ledger
        )

    async def list_by_owner(self, owner_id: str) -> List[Project]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ProjectDB).where(ProjectDB.owner_id == owner_id).order_by(ProjectDB.updated_at.desc())
            )
            rows = result.scalars().all()
            return [
                Project(
                    id=UUID(r.id),
                    name=r.name,
                    owner_id=r.owner_id,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    nodes={},
                    assets=r.assets or {},
                    asset_ledger=AssetLedger(**(r.asset_ledger or {}))
                )
                for r in rows
            ]

    async def save(self, project: Project, session: Optional[AsyncSession] = None) -> None:
        """Full Upsert (Overwrite). Use update_node_state for concurrent operations."""
        if session:
            await self._save_impl(session, project)
        else:
            async with AsyncSessionLocal() as local_session:
                async with local_session.begin():
                    await self._save_impl(local_session, project)

    async def _save_impl(self, session: AsyncSession, project: Project) -> None:
        row = await session.get(ProjectDB, str(project.id))
        ledger_dump = project.asset_ledger.model_dump(mode="json")
        if row:
            row.name = project.name
            row.updated_at = datetime.utcnow()
            row.assets = project.assets
            row.asset_ledger = ledger_dump
        else:
            session.add(ProjectDB(
                id=str(project.id), owner_id=project.owner_id, name=project.name,
                created_at=project.created_at,
                updated_at=project.updated_at,
                assets=project.assets,
                asset_ledger=ledger_dump
            ))
            await session.flush()

        for _, ns in project.nodes.items():
            await self.upsert_node_state(ns, str(project.id), session)

    async def delete(self, project_id: UUID) -> bool:
        """[NEW] Delete project and related state."""
        pid_str = str(project_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Check existence
                row = await session.get(ProjectDB, pid_str)
                if not row:
                    return False
                
                # Delete dependencies (Cascade logically)
                # Note: DB cascade is preferred, but explicit here for safety with SQLModel
                await session.execute(delete(NodeStateDB).where(NodeStateDB.project_id == pid_str))
                await session.execute(delete(NodeVersionDB).where(NodeVersionDB.project_id == pid_str))
                await session.execute(delete(ProjectDB).where(ProjectDB.id == pid_str))
                return True

    async def update_node_state(self, project_id: UUID, node_state: NodeState, session: Optional[AsyncSession] = None) -> None:
        """[FIX Issue 3] Wrapper for Atomic Node Update."""
        pid_str = str(project_id)
        if session:
            await self.upsert_node_state(node_state, pid_str, session)
            await session.execute(update(ProjectDB).where(ProjectDB.id == pid_str).values(updated_at=datetime.utcnow()))
        else:
            async with AsyncSessionLocal() as local:
                async with local.begin():
                    await self.upsert_node_state(node_state, pid_str, local)
                    await local.execute(update(ProjectDB).where(ProjectDB.id == pid_str).values(updated_at=datetime.utcnow()))

    async def upsert_node_state(self, ns: NodeState, project_id: str, session: AsyncSession) -> None:
        """Best-effort cross-dialect upsert for SQLite and PostgreSQL."""
        result = await session.execute(
            select(NodeStateDB).where(
                NodeStateDB.project_id == project_id,
                NodeStateDB.node_id == ns.node_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.base_id = ns.base_id
            existing.iteration_index = ns.iteration_index
            existing.status = ns.status.value
            existing.stable_version_id = str(ns.stable_version_id) if ns.stable_version_id else None
            existing.working_version_id = str(ns.working_version_id) if ns.working_version_id else None
            existing.updated_at = ns.updated_at
            return

        session.add(
            NodeStateDB(
                project_id=project_id,
                node_id=ns.node_id,
                base_id=ns.base_id,
                iteration_index=ns.iteration_index,
                status=ns.status.value,
                stable_version_id=str(ns.stable_version_id) if ns.stable_version_id else None,
                working_version_id=str(ns.working_version_id) if ns.working_version_id else None,
                updated_at=ns.updated_at,
            )
        )


class VersionRepository:

    # [FIX] Helper function to sanitize JSON-compatible structures
    def _sanitize_json_structure(self, data: Any) -> Any:
        """
        Recursively removes Null bytes from strings within dicts/lists.
        Required for PostgreSQL JSONB compatibility.
        """
        if isinstance(data, str):
            return data.replace("\x00", "")
        elif isinstance(data, dict):
            return {k: self._sanitize_json_structure(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_json_structure(v) for v in data]
        else:
            return data

    def _serialize_and_truncate(self, outputs: List[Any], version_id: Any) -> List[Dict]:
        # SQLite limit is usually 1GB, but for performance/safety, we cap at 50MB per version row
        MAX_JSON_SIZE = 50 * 1024 * 1024  # 50MB
        safe_outputs = [o.model_dump(mode="json") for o in outputs]
        
        # [FIX] Apply sanitization before serialization
        safe_outputs = self._sanitize_json_structure(safe_outputs)
        
        serialized = json.dumps(safe_outputs)
        if len(serialized) > MAX_JSON_SIZE:
            logger.error(
                f"CRITICAL: NodeVersion {version_id} outputs size ({len(serialized)} bytes) exceeds safety limit. "
                "Truncating."
            )
            return [{
                "blocks": [{
                    "type": "MARKDOWN",
                    "label": "System Error",
                    "content": "CRITICAL: Output size exceeded database limits. Data was truncated to prevent crash.",
                    "tags": ["error"]
                }],
                "metadata": {"error": "PAYLOAD_TOO_LARGE"}
            }]
        return safe_outputs
    
    async def create(self, version: NodeVersion, session: Optional[AsyncSession] = None) -> None:
        if session: await self._create_impl(session, version)
        else:
            async with AsyncSessionLocal() as s:
                async with s.begin(): await self._create_impl(s, version)

    async def _create_impl(self, session: AsyncSession, version: NodeVersion):
        safe_outputs = self._serialize_and_truncate(version.outputs, version.id)
        
        # [FIX] Sanitize Provenance (Input Snapshot usually lives here)
        safe_provenance = self._sanitize_json_structure(version.provenance or {})
        
        row = NodeVersionDB(
            id=str(version.id), 
            project_id=str(version.project_id), 
            node_id=version.node_id,
            created_at=version.created_at, 
            outputs=safe_outputs, 
            provenance=safe_provenance
        )
        session.add(row)

    async def update_draft(self, version: NodeVersion, session: Optional[AsyncSession] = None) -> None:
        if session: await self._update_impl(session, version)
        else:
            async with AsyncSessionLocal() as s:
                async with s.begin(): await self._update_impl(s, version)

    async def _update_impl(self, session: AsyncSession, version: NodeVersion):
        existing = await session.get(NodeVersionDB, str(version.id))
        safe_outputs = self._serialize_and_truncate(version.outputs, version.id)
        
        # [FIX] Sanitize Provenance here too
        safe_provenance = self._sanitize_json_structure(version.provenance or {})
        
        if existing:
            existing.outputs = safe_outputs
            existing.provenance = safe_provenance
            existing.updated_at = datetime.utcnow()
        else:
            await self._create_impl(session, version)

    async def get(self, version_id: UUID, session: Optional[AsyncSession] = None) -> Optional[NodeVersion]:
        if session: return await self._get_impl(session, version_id)
        else:
            async with AsyncSessionLocal() as s: return await self._get_impl(s, version_id)

    async def _get_impl(self, session: AsyncSession, version_id: UUID) -> Optional[NodeVersion]:
        row = await session.get(NodeVersionDB, str(version_id))
        if not row: return None
        from app.domain.unified_io import NodeOutput
        outputs = [NodeOutput(**o) for o in (row.outputs or []) if o]
        return NodeVersion(
            id=UUID(row.id), project_id=UUID(row.project_id), node_id=row.node_id,
            created_at=row.created_at, outputs=outputs, provenance=row.provenance or {}
        )
    
    async def get_batch(self, version_ids: List[UUID]) -> List[NodeVersion]:
        if not version_ids: return []
        str_ids = [str(vid) for vid in version_ids]
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(NodeVersionDB).where(NodeVersionDB.id.in_(str_ids)))
            rows = result.scalars().all()
            from app.domain.unified_io import NodeOutput
            versions = []
            for row in rows:
                outputs = [NodeOutput(**o) for o in (row.outputs or []) if o]
                versions.append(NodeVersion(id=UUID(row.id), project_id=UUID(row.project_id), node_id=row.node_id, created_at=row.created_at, outputs=outputs, provenance=row.provenance or {}))
            return versions

    async def list_summaries_by_node(self, project_id: UUID, node_id: str) -> List[Dict[str, Any]]:
        """
        [NEW] List version metadata only (for History UI).
        Excludes the heavy 'outputs' column to be lightweight.
        """
        async with AsyncSessionLocal() as session:
            # Select specific columns only
            query = select(
                NodeVersionDB.id, 
                NodeVersionDB.created_at, 
                NodeVersionDB.provenance
            ).where(
                NodeVersionDB.project_id == str(project_id),
                NodeVersionDB.node_id == node_id
            ).order_by(NodeVersionDB.created_at.desc())
            
            result = await session.execute(query)
            rows = result.all()
            
            summaries = []
            for r in rows:
                prov = r.provenance or {}
                summaries.append({
                    "id": UUID(r.id),
                    "created_at": r.created_at,
                    "trigger": prov.get("trigger", "UNKNOWN"),
                    "intent": prov.get("intent", "generate"),
                    # Try to extract stats from inputs_snapshot if possible, or we could store stats separate
                    "meta": prov
                })
            return summaries
