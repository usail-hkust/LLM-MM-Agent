"""
Domain Events - SSE Event Schemas.

Defines the schemas for events broadcasted via the Event Bus (SSE).
"""
from pydantic import BaseModel, Field
from typing import Any, Dict
from datetime import datetime
from app.core.definitions import NodeStatus


class DomainEvent(BaseModel):
    """Base class for all domain events."""
    event: str
    data: Dict[str, Any]
    # [FIX Issue 2] Use Millisecond Timestamp (float) to match JS 'number' type
    # Frontend expects: timestamp: number (e.g. 1699999999123)
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp() * 1000)


class NodeStatusEvent(DomainEvent):
    """Event for node status changes."""
    def __init__(self, node_id: str, status: NodeStatus):
        super().__init__(
            event="NODE_STATUS", 
            data={"node_id": node_id, "status": status.value}
        )


class NodeUpdateEvent(DomainEvent):
    """
    Payload containing the full NodeVersion data.
    Triggered when a draft is generated or updated.
    """
    def __init__(self, node_id: str, version_data: Dict[str, Any]):
        super().__init__(
            event="NODE_UPDATE",
            data={"node_id": node_id, "version": version_data}
        )


class ExecutionLogEvent(DomainEvent):
    """
    Streaming logs from the Sandbox or LLM generation process.
    """
    def __init__(self, node_id: str, content: str, stream: str = "stdout"):
        super().__init__(
            event="EXEC_LOG", 
            data={"node_id": node_id, "content": content, "stream": stream}
        )


class TimelineUpdateEvent(DomainEvent):
    """
    Triggered when the project structure changes (e.g. Commit unlocks new nodes).
    """
    def __init__(self, project_id: str):
        super().__init__(
            event="TIMELINE_UPDATE",
            data={"project_id": project_id}
        )


class ErrorEvent(DomainEvent):
    """Error event."""
    def __init__(self, message: str, code: str = "ERROR"):
        super().__init__(
            event="ERROR",
            data={"message": message, "code": code}
        )

