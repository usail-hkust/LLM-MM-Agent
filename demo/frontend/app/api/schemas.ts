import { WorkflowStatus, LayoutMode, BlockType, ActionType } from "./enums";
import { ContentBlock, ActionInputSpec, RenderAction } from "@/app/domain/abp";

// Re-export enums for convenience
export { WorkflowStatus, LayoutMode, BlockType, ActionType };
// Re-export domain types from canonical source
export type { ContentBlock, ActionInputSpec, RenderAction } from "@/app/domain/abp";

export interface ProjectSummary {
  id: string;
  name: string;
  updated_at: string;
}

export interface ProjectStatusResponse {
  id: string;
  name?: string;
  status?: string; // Can be "RUNNING" or other status values
  [key: string]: any; // Allow additional fields
}

export interface TimelineNode {
  id: string;
  base_id: string;
  title: string;
  status: WorkflowStatus;
  // [NEW] Added phase field
  phase: string;
  iteration_index: number;
  is_structural_driver: boolean;
}

export interface TimelineResponse {
  project_id: string;
  name: string;
  nodes: TimelineNode[];
  // [NEW] Explicit guidance from backend
  suggested_next_node?: string;
}


export interface NodeState {
  status: WorkflowStatus;
  layout_mode: LayoutMode;
  is_read_only: boolean;
  blocks: ContentBlock[];
  allowed_actions?: RenderAction[];
  active_version_id?: string | null;
  global_actions?: RenderAction[];
  metadata?: Record<string, any>;
}

export interface NodeWorkspaceView {
  definition: { type: string; ux_config?: Record<string, any> };
  state: NodeState;
}

export interface InteractionRequest {
  action: string;
  node_id?: string; // Optional, extracted from URL path in backend
  payload: Record<string, any>;
}

export interface AssetUploadResponse {
  manifest: Record<string, string>;
}

export interface ServerEvent {
  type: "NODE_STATUS" | "NODE_UPDATE" | "TIMELINE_UPDATE" | "EXEC_LOG" | "ERROR";
  [key: string]: any;
}

// [REFACTORED] Linear History Models
export interface HistoryArtifact {
  id: string;
  type: string;
  timestamp: number;
  status: string;
  data?: any;
  summary?: string;
}

export interface UnifiedHistoryEntry {
  id: string;
  node_id: string;
  version_index: number;
  timestamp: string;
  status: string;
  trigger: string;
  parent_id?: string | null;
  data?: Record<string, any> | null;
  artifacts: HistoryArtifact[];
  permissions: Record<string, boolean>;
  meta: Record<string, any>;
}

export interface NodeHistoryResponse {
  timeline: UnifiedHistoryEntry[];
}
