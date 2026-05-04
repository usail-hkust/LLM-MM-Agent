"""
Static Workflow Definitions.

Defines the static topology of the workflow.
[Updated] Added support for multi-template intents (Unified Interaction Loop).
[Enhanced] Added InteractionPolicy for fine-grained rendering control.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator

from app.core.definitions import NodeType, RenderType, LayoutMode


class InteractionPolicy(BaseModel):
    """
    Defines the static capabilities of a node type.
    """
    # Can the user trigger a re-run/re-generate?
    can_reexecute: bool = False
    
    # Can the user edit the text/code content directly?
    can_edit_content: bool = False
    
    # Is this a selection node (SCA)?
    can_select_alternatives: bool = False
    
    # Does it require explicit approval to proceed?
    approval_required: bool = True


class UXConfig(BaseModel):
    """Presentation hints."""
    # Structural template
    layout_mode: LayoutMode = LayoutMode.STANDARD
    
    # Default component for content blocks
    primary_view: RenderType = RenderType.MARKDOWN_VIEWER
    
    # Toggles
    show_console: bool = False
    show_artifacts: bool = False


class IterationStrategy(BaseModel):
    """
    Defines how a node spawns multiple instances based on an upstream list.
    """
    driver_node_id: str          # The ID of the node producing the list (e.g., "1.2")
    driver_output_tag: str       # The tag in the driver's output containing the list (e.g., "sub_problem_list")
    context_slice_key: str       # The key to inject the specific item into inputs (e.g., "current_sub_task")


class OutputSpec(BaseModel):
    """
    [NEW] Output Anchor Specification.
    Defines the expected output format constraints to help PromptFactory
    inject the correct 'Anchor' instructions (L2 Protocol).
    """
    expected_type: str  # 'json', 'code', 'latex'
    target_label: str   # e.g., 'paper_blueprint', 'data_loader'


class NodeBlueprint(BaseModel):
    """
    [Static Definition]
    Defines the behavior and template for a workflow step.
    
    [Unified Interaction]
    Supports multiple templates mapped by intent (generate/critique/refine).
    
    [Topology Control]
    Supports structural drivers (is_structural) and iterative nodes (iteration).
    """
    id: str
    title: str
    phase_label: str = "General"
    
    node_type: NodeType
    
    # [Unified Interaction]
    # Replaces single 'template_ref'. Maps Intent -> Template Path.
    # Standard intents: "generate" (default), "critique", "refine".
    templates: Dict[str, str] = Field(default_factory=dict)
    
    # [Topology Controls]
    is_structural: bool = False  # If True, its output drives downstream topology
    iteration: Optional[IterationStrategy] = None  # If set, this node is dynamic (1:N)
    
    ux: UXConfig = Field(default_factory=UXConfig)
    
    # [NEW] Capabilities
    interaction: InteractionPolicy = Field(default_factory=InteractionPolicy)
    
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    # [NEW] Output specification for Dual-Anchor Protocol
    output_spec: Optional[OutputSpec] = None
    
    def get_template_for_intent(self, intent: str) -> str:
        """
        Resolves template path based on intent, falling back to default.
        
        Fallback chain: exact match -> "generate" -> "default" -> ""
        """
        # 1. Try exact match
        if intent in self.templates:
            return self.templates[intent]
        # 2. Try 'generate' or 'default'
        return self.templates.get("generate") or self.templates.get("default", "")

