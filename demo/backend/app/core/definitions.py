"""
Core definitions - Enums and Constants.

Consolidates all enums and constants from common/, domain/, and other modules.
This is the single source of truth for type definitions.
"""
from enum import Enum


# --- Enums ---

class NodeType(str, Enum):
    """Primary behavior of the node runner."""
    GENERATOR = "GENERATOR"  # Pure LLM Generation (Text/Plan)
    EXECUTOR = "EXECUTOR"    # LLM Generation + Code Execution (Sandbox)


class NodeStatus(str, Enum):
    """Lifecycle state of a single node."""
    VOID = "VOID"             # Not started / No data
    LOCKED = "LOCKED"         # Locked due to dependencies
    DRAFTING = "DRAFTING"     # Processing (LLM generating or Code running)
    REVIEWING = "REVIEWING"   # Interactive state (Drafts available, waiting for user)
    FAILED = "FAILED"         # Execution failed explicitly
    COMMITTED = "COMMITTED"   # Finalized (Effective payload generated)
    STALE = "STALE"           # Data exists but upstream dependency has changed
    OBSOLETE = "OBSOLETE"     # Valid but not the current head (for versions that are valid but not the current head)


class VersionTrigger(str, Enum):
    """Semantics for why a version exists in the linear chain."""
    INITIAL_RUN = "INITIAL_RUN"  # First execution
    REFINE = "REFINE"            # Iteration based on feedback (Reject & Regenerate)
    SELECT = "SELECT"            # Selection of a specific option (Convergence)
    EDIT = "EDIT"                # Manual edit
    RESTORE = "RESTORE"          # Time travel restore
    FORK = "FORK"                # Branching


class BlockType(str, Enum):
    """Structural type of a ContentBlock."""
    MARKDOWN = "MARKDOWN"
    CODE = "CODE"
    DATA = "DATA"           # Structured JSON
    FILE = "FILE"           # Binary Asset Reference
    CONTAINER = "CONTAINER" # Recursive Layout


class RenderType(str, Enum):
    """UI Component Routing Hints."""
    DEFAULT = "DEFAULT"
    MARKDOWN_VIEWER = "MARKDOWN_VIEWER"
    CODE_EDITOR = "CODE_EDITOR"
    IDE_WORKSPACE = "IDE_WORKSPACE"
    SCA_OPTION_CARD = "SCA_OPTION_CARD"  # Selection Card
    SCA_PLAN_CARD = "SCA_PLAN_CARD"  # Editable Plan Card
    DATA_VIEWER = "DATA_VIEWER"
    ARTIFACT_GALLERY = "ARTIFACT_GALLERY"
    LOG_CONSOLE = "LOG_CONSOLE"  # [FIX] Added for SmartConsole routing
    VARL_ANALYSIS = "VARL_ANALYSIS"
    RESULT_SUMMARY = "RESULT_SUMMARY"
    AVL_CRITIQUE_CARD = "AVL_CRITIQUE_CARD"
    CONTAINER_STACK = "CONTAINER_STACK"
    CONTAINER_GRID = "CONTAINER_GRID"
    CONTAINER_TABS = "CONTAINER_TABS"
    CONTAINER_SPLIT = "CONTAINER_SPLIT"
    INPUT_TEXT = "INPUT_TEXT"


class ContestType(str, Enum):
    """Supported contest types."""
    MCM = "MCM"
    ICM = "ICM"


# --- Layout & Interaction Enums ---

class LayoutMode(str, Enum):
    """High-level UI Intent."""
    STANDARD = "STANDARD"       # Linear stream
    WORKBENCH = "WORKBENCH"     # Split: Editor + Preview
    SELECTION = "SELECTION"     # Grid: Options
    REVIEW = "REVIEW"           # Split: Doc + Critiques
    DOCUMENT = "DOCUMENT"       # Vertical Stack Editor
    FOCUS = "FOCUS"             # [NEW] Single column full-width (Code/Content Focused)


class ActionType(str, Enum):
    """Visual Semantics for Actions."""
    PRIMARY = "primary"         # Blue/Solid
    SECONDARY = "secondary"     # Gray/Outline
    DANGER = "danger"           # Red
    ICON = "icon"               # Icon only
    TRIGGER_SHEET = "TRIGGER_SHEET"  # Open modal/sheet


# [NEW] Action Scoping Protocol
class ActionScope(str, Enum):
    """Defines where an action should be rendered in the UI."""
    BLOCK = "BLOCK"             # Bind to component Header (e.g. Save, Copy, Run Code)
    WORKSPACE = "WORKSPACE"     # Bind to global Dock (e.g. Approve, Reset)


# --- System Tags ---

class SystemTags:
    """Unified system tag definitions for log identification."""
    LOGS = "logs"
    EXECUTION_LOGS = "execution_logs"
    STDOUT = "stdout"
    STDERR = "stderr"
    THOUGHT = "thought"  # [NEW] For unified narrative
    ERROR = "error"
    
    # [REFACTOR] 语义标签契约
    # 任何导致节点失败的关键错误信息，必须包含此 Tag
    # 消费者（Auto-Recovery）只认这个 Tag，不认 Label
    PRIMARY_ERROR = "primary_error"
    
    # Set for quick lookup
    ALL_LOGS = {LOGS, EXECUTION_LOGS, STDOUT, STDERR, THOUGHT, ERROR, PRIMARY_ERROR}
