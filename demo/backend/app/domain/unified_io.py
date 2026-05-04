"""
Atomic Block Protocol (ABP) - Enhanced with Interaction.

This module defines the single source of truth for all node outputs in the system.
All LLM adapters, services, and engines must produce and consume NodeOutput objects.

[Enhanced with Dynamic Actions]
- Restored UI/Action logic (ActionInputSpec, RenderAction) for fine-grained rendering control.
- ContentBlock enriched with dynamic actions that are injected at runtime.
- Optimized serialization for LLM Context (actions are stripped).
"""
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict

from app.core.definitions import BlockType, RenderType, ActionType, SystemTags, ActionScope


# [NEW] Internal DTO for Streaming Chat
class CopilotStreamChunk(BaseModel):
    """
    Standardized chunk for Copilot streaming.
    Decouples 'content' (Answer) from 'thought' (Reasoning/CoT).
    """
    content: str = ""
    thought: str = ""  # For DeepSeek R1 or other CoT models
    finish_reason: Optional[str] = None


# --- Interaction Primitives ---

class ActionInputSpec(BaseModel):
    """
    Defines if an action requires user input before submission.
    """
    type: Literal["text", "textarea", "confirmation"]
    label: str
    key: str  # The key to inject into the payload
    required: bool = False
    default_value: Optional[str] = None


class RenderAction(BaseModel):
    """
    Dynamic control definition sent to the frontend.
    Allows the backend to dictate valid state transitions per block.
    """
    id: str
    label: str
    type: ActionType = ActionType.SECONDARY
    icon: Optional[str] = None
    
    # The payload to be sent back to 'handle_interaction'
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Frontend behavior hints
    validation_rule: Optional[Literal["require_dirty", "always_enabled"]] = None
    confirm_message: Optional[str] = None
    input_spec: Optional[ActionInputSpec] = None
    
    # [NEW] Action Scoping Protocol
    scope: ActionScope = ActionScope.WORKSPACE


# --- Block Definition ---

class ContentBlock(BaseModel):
    """
    [Atomic Unit]
    Carries Data (content) and Behavior (actions).
    
    Design Changes:
    - Recursive: Supports nested children for layout (CONTAINER type).
    - Dynamic Actions: Actions are usually injected at runtime by ViewAssembler, 
      but can be persisted if specific to a version.
    - Polymorphic: 'content' can be string, list, or dict.
    """
    model_config = ConfigDict(from_attributes=True)

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()), description="Global Unique ID")
    
    # Classification
    type: BlockType = Field(..., description="Structural type.")
    label: str = Field(..., description="Human-readable header.")
    
    # Payload
    content: Any = Field(None, description="The payload (String, Dict, or List).")

    # Structure (Recursive)
    children: List["ContentBlock"] = Field(default_factory=list)

    # Hints
    render_type: RenderType = RenderType.DEFAULT
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    # [RE-INTRODUCED] Dynamic Actions
    # These are usually injected at runtime by ViewAssembler, 
    # but can be persisted if specific to a version.
    actions: List[RenderAction] = Field(default_factory=list)

    # [CRITICAL FIX] Data Binding Key
    # Enables explicit two-way binding between the UI component and the form state.
    # If present, the component becomes editable. If null, it remains read-only.
    data_key: Optional[str] = Field(default=None, description="Runtime binding key for form editing. If null, block is read-only.")

    def to_llm_context(self) -> Dict[str, Any]:
        """
        Sanitized dict for LLM prompts (actions are stripped).
        """
        if self.type == BlockType.CONTAINER:
            return {
                "type": self.type.value,
                "label": self.label,
                "children": [c.to_llm_context() for c in self.children],
                "tags": self.tags
            }

        val = self.content
        if isinstance(val, str) and len(val) > 20000:
            val = val[:20000] + "\n... [TRUNCATED] ..."

        # Allowlist meta
        meta_keys = {"language", "mime_type", "filename", "error", "status"}
        safe_meta = {k: v for k, v in self.meta.items() if k in meta_keys}

        return {
            "type": self.type.value,
            "label": self.label,
            "content": val,
            "tags": self.tags,
            "meta": safe_meta
        }

    def to_ui_dict(self) -> Dict[str, Any]:
        """
        Full fidelity dict for frontend rendering.
        Includes render_type, actions, and all meta.
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "content": self.content,
            "render_type": self.render_type.value if self.render_type else None,
            "tags": self.tags,
            "meta": self.meta,
            "actions": [a.model_dump() for a in self.actions],
            "data_key": self.data_key,
            "children": [c.to_ui_dict() for c in self.children]
        }


# Handle recursive Pydantic definition (needed for forward references)
ContentBlock.model_rebuild()


class NodeOutput(BaseModel):
    """
    [Universal Payload]
    Standard container for LLM generation, Sandbox execution, and API responses.
    Represents the result of a single computation unit (Compute).
    """
    model_config = ConfigDict(from_attributes=True)

    # [FIX] Added missing 'thought' field to match frontend protocol and ViewAssembler logic
    thought: Optional[str] = Field(default="", description="Chain of Thought reasoning.")

    blocks: List[ContentBlock] = Field(default_factory=list)
    
    # Runtime Data: Logs, usage stats, execution time, errors
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Selection State (Used when aggregating multiple outputs in a Version)
    is_selected: bool = Field(default=False)

    def get_block(self, tag_or_type: str) -> Optional[ContentBlock]:
        """Helper to find the first block matching a tag, type, or label (case-insensitive)."""
        search = tag_or_type.lower()
        queue = list(self.blocks)
        while queue:
            block = queue.pop(0)
            # 1. Check Type
            if block.type.value.lower() == search:
                return block
            # 2. Check Tags
            if any(t.lower() == search for t in block.tags):
                return block
            # 3. Check Label (Critical for finding 'Stdout', 'Stderr' blocks)
            if block.label.lower() == search:
                return block
            if block.children:
                queue.extend(block.children)
        return None

    def get_primary_error(self) -> Optional[str]:
        """
        [REFACTORED] 获取导致失败的核心错误信息。
        不再依赖 Label 字符串匹配，而是查找 SystemTags.PRIMARY_ERROR。
        """
        # 1. 优先查找明确标记为 PRIMARY_ERROR 的块
        for block in self.blocks:
            if SystemTags.PRIMARY_ERROR in block.tags:
                return str(block.content)
            # 递归查找子块
            if block.children:
                for child in block.children:
                    if SystemTags.PRIMARY_ERROR in child.tags:
                        return str(child.content)
        
        # 2. 只有在找不到显式 Error Block 且 exit_code != 0 时，
        # 才进行极其有限的兜底（比如找 stderr），或者直接返回 Generic Message
        if self.metadata.get("exit_code", 0) != 0:
            # 查找 stderr 作为次选
            for block in self.blocks:
                if SystemTags.STDERR in block.tags:
                    return str(block.content)
                # 递归查找子块
                if block.children:
                    for child in block.children:
                        if SystemTags.STDERR in child.tags:
                            return str(child.content)
            return "Unknown Error (Exit Code non-zero, but no error log found)."
            
        return None

    def to_context_dict(self) -> Dict[str, Any]:
        """
        Prepares the output for inclusion in downstream LLM history context.
        Excludes metadata to save tokens.
        """
        return {
            "thought": self.thought,  # [FIX] Include thought in context
            "blocks": [b.to_llm_context() for b in self.blocks]
        }

    def to_ui_dict(self) -> Dict[str, Any]:
        """
        Full fidelity dict for UI snapshot in history.
        """
        return {
            "thought": self.thought,
            "blocks": [b.to_ui_dict() for b in self.blocks],
            "metadata": self.metadata
        }
