import type { ReactNode } from "react";
import { BlockType, ActionType } from "@/app/api/enums";

/**
 * Atomic Block Protocol (ABP) - Frontend Definition
 * Mirrors backend: app.domain.unified_io
 *
 * This is the Single Source of Truth for the data structure of a Block.
 * All business logic (Code execution, Paper generation, SCA selection)
 * must be encapsulated within this protocol.
 */

// Re-export Enums for convenience/backward-compatibility
export { BlockType, ActionType };

export enum ActionScope {
  BLOCK = "BLOCK",
  WORKSPACE = "WORKSPACE"
}

// [SSoT] 统一绑定键解析策略
// 优先级：后端指定 Key > 组件 ID > Null (无交互)
export function resolveBindingKey(block: any): string | null {
  // [CRITICAL FIX] Defensive Guard for undefined block
  if (!block) return null;

  // 1. 纯展示组件跳过
  if (!block.data_key && (block.type === BlockType.MARKDOWN || block.type === BlockType.CONTAINER || block.type === BlockType.FILE)) {
    return null;
  }
  // 2. 优先使用后端语义 Key (e.g. "code", "user_feedback")
  if (block.data_key) return block.data_key;
  
  // 3. 交互组件兜底使用 ID
  const INTERACTIVE_TYPES = new Set([BlockType.CODE, BlockType.DATA, "INPUT_TEXT", "CODE_EDITOR"]);
  if (INTERACTIVE_TYPES.has(block.type) || (block.render_type && INTERACTIVE_TYPES.has(block.render_type))) {
    return block.id;
  }
  return null;
}

// [ARCH-FIX] Explicit UI Routing Contract
export enum RenderType {
  DEFAULT = "DEFAULT",
  SCA_OPTION_CARD = "SCA_OPTION_CARD",
  SCA_PLAN_CARD = "SCA_PLAN_CARD",
  AVL_CRITIQUE_CARD = "AVL_CRITIQUE_CARD",
  CODE_EDITOR = "CODE_EDITOR",
  MARKDOWN_VIEWER = "MARKDOWN_VIEWER",
  DATA_VIEWER = "DATA_VIEWER",
  ARTIFACT_GALLERY = "ARTIFACT_GALLERY",
  LOG_CONSOLE = "LOG_CONSOLE",
  CONTAINER_GRID = "CONTAINER_GRID",
  CONTAINER_STACK = "CONTAINER_STACK",
  CONTAINER_TABS = "CONTAINER_TABS",
  CONTAINER_SPLIT = "CONTAINER_SPLIT",
  INPUT_TEXT = "INPUT_TEXT",
  VARL_ANALYSIS = "VARL_ANALYSIS",
  RESULT_SUMMARY = "RESULT_SUMMARY",
  IDE_WORKSPACE = "IDE_WORKSPACE"
}

// [FIX] Define Self-Contained Render Types
// These widgets render their own action buttons internally and SHOULD NOT
// broadcast them to the global Dock. This prevents duplication and state chaos.
export const SELF_CONTAINED_RENDER_TYPES = new Set<RenderType | string>([
  RenderType.SCA_OPTION_CARD,
  RenderType.SCA_PLAN_CARD,
  RenderType.AVL_CRITIQUE_CARD,
  RenderType.VARL_ANALYSIS
]);

// --- Interaction & Action Types ---

export interface ActionInputSpec {
  type: "text" | "textarea" | "select";
  label: string; // The prompt message
  key: string; // The key to inject into the payload
  required?: boolean;
  default_value?: string | null;
  options?: string[]; // For "select" type
}

export interface RenderAction {
  id: string; // Unique identifier (e.g., "submit_varl_code")
  label: string; // Button text
  type: ActionType; // Visual style variant
  scope?: ActionScope | string; // [NEW] Scope
  icon?: string | null; // Optional Lucide icon name (e.g., "Play", "Save")
  payload?: Record<string, any>; // Action payload merged with form data
  confirm_message?: string | null; // Optional confirmation prompt
  /**
   * Frontend Validation Logic
   * Controls the disabled state of the button without backend round-trips.
   * - "require_dirty": Enabled only if FormData has changes (e.g., "Save").
   * - "always_enabled": Always enabled (Default).
   */
  validation_rule?: "require_dirty" | "always_enabled" | null;
  /**
   * Dynamic input requirement before triggering the action.
   * If present, frontend will collect user input and merge it into the payload.
   */
  input_spec?: ActionInputSpec | null;
}

// --- Rendering Context Types (Frontend Only) ---

export interface RenderState {
  /**
   * Global Interactivity Lock.
   * - true: History/Snapshot Mode. Inputs become text, Editors become read-only.
   * - false: Live/Interactive Mode.
   */
  read_only: boolean;

  /**
   * Visibility flag. Allows for progressive disclosure or hidden state carriers.
   */
  visible: boolean;

  /**
   * [Core] Two-Way Binding Path.
   * - If present (e.g., "new_content.code"):
   *   The component is in "Edit Mode". Initial value comes from `block.content`,
   *   but changes are written to `RenderContext.formData["new_content.code"]`.
   * - If absent:
   *   The component is in "Display Mode". It strictly renders `block.content`.
   */
  data_key?: string;
}

export interface ContentBlock {
  id: string;             // [Key Fix] Global Unique ID
  render_type?: RenderType;// [Route Fix] Explicit Widget
  type: BlockType;
  label: string;

  // Polymorphic payload
  content: string | Record<string, any> | any[] | null;

  // [SDUI] Recursive Structure
  children?: ContentBlock[];

  // [SDUI] Layout Configuration
  // e.g. { kind: "SPLIT", orientation: "horizontal" }
  layout?: Record<string, any>;

  tags: string[];
  meta: Record<string, any>;
  actions?: RenderAction[];

  /**
   * [CRITICAL FIX] Data Binding Key.
   * Passed from backend. If present, it maps to `state.data_key` in the renderer,
   * enabling `useAtomBinding` to activate edit mode.
   */
  data_key?: string;
}

export interface NodeOutput {
  /**
   * Chain of Thought (Mandatory)
   * The reasoning process provided before generating blocks.
   */
  thought: string;

  /**
   * Ordered stream of Content Blocks
   */
  blocks: ContentBlock[];

  /**
   * System-level sidecar data (Legacy/Private fields)
   */
  metadata?: Record<string, any>;
}

/**
 * Standard Props for any Atomic Block Component (Atom or Layout)
 */
export interface RenderAtomProps {
  /**
   * Core Data Unit (Backbone)
   */
  block: ContentBlock;

  /**
   * Runtime Contextual State
   */
  state: RenderState;

  /**
   * Interactive Actions
   */
  actions: RenderAction[];

  /**
   * Action Callback
   */
  onAction: (action: RenderAction) => void;

  /**
   * Auxiliary Context
   */
  isSubmitting?: boolean;
  blockId?: string; // For React Key or DOM ID
  children?: ReactNode;
}

// --- Type Guards ---

/**
 * Runtime type check for NodeOutput.
 */
export function isNodeOutput(data: any): data is NodeOutput {
  return (
    data &&
    typeof data === "object" &&
    Array.isArray(data.blocks) &&
    typeof data.thought === "string"
  );
}

/**
 * Helper to check block type
 */
export function isBlockType(block: ContentBlock, type: BlockType): boolean {
  return block.type === type;
}

/**
 * [FIX] Global Visibility Guard (Third Line of Defense)
 * Determines if a block should be rendered at all.
 * Used by Layouts to filter out "ghost" blocks before they hit the DOM.
 */
export function isBlockVisible(block: ContentBlock): boolean {
  // 1. Explicit Protocol Override
  if (block.meta?.render_state === "HIDDEN" || block.meta?.visibility === "hidden") {
    return false;
  }

  // 2. Allow Special Components (Even if content seems empty)
  // SmartConsole handles its own "Ready" state
  if (block.render_type === RenderType.LOG_CONSOLE) return true;
  // Code Editor must exist to allow typing
  if (block.type === BlockType.CODE || block.render_type === RenderType.CODE_EDITOR) return true;
  // File placeholder
  if (block.type === BlockType.FILE) return true;
  // Input Component
  if (block.render_type === RenderType.INPUT_TEXT) return true;

  // 3. Content-Based Filtering
  // Markdown: Must have non-whitespace characters
  if (block.type === BlockType.MARKDOWN) {
    return !!String(block.content || "").trim();
  }

  // Data: Must have keys or items
  if (block.type === BlockType.DATA) {
    // SCA Cards are complex, assume visible if they exist (Parser filters ghost SCAs)
    if (block.render_type === RenderType.SCA_OPTION_CARD || block.render_type === RenderType.SCA_PLAN_CARD) {
        return true;
    }
    
    if (!block.content) return false;
    if (Array.isArray(block.content) && block.content.length === 0) return false;
    if (typeof block.content === 'object' && Object.keys(block.content).length === 0) return false;
  }

  // Container: Recursive check? 
  // Usually containers are structural. If empty children, maybe hide?
  // For now, assume containers are valid if backend sent them.
  
  return true;
}
