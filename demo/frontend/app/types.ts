import type { LucideIcon } from "lucide-react";
import { UnifiedHistoryEntry, WorkflowStatus } from "@/app/lib/api-types";

// [UPDATED] Unified type entry point
// 1. Re-export Domain Protocols
export * from "./domain/abp";

// 2. Re-export API Types (Enums & DTOs)
export * from "@/app/lib/api-types";

// 3. Frontend Utilities
export type JsonLike =
  | string
  | number
  | boolean
  | null
  | JsonLike[]
  | { [key: string]: JsonLike };

/**
 * 状态视觉语义标识
 * 用于将后端业务逻辑映射为前端视觉语言的中间层
 */
export type StatusVariant =
  | "running"
  | "pending"
  | "success"
  | "error"
  | "warning"
  | "idle"
  | "default";

/**
 * 状态动画定义
 */
export interface StatusAnimation {
  type: "spin" | "pulse" | "ping" | "none";
  className: string;
}

/**
 * 视觉主题配置
 * 包含全套 Tailwind 原子类，确保全站颜色的一致性
 */
export interface StatusTheme {
  text: string;
  bg: string;
  border: string;
  dot: string;
  ring: string;
}

/**
 * 统一的状态视觉配置对象 (Status Identity Config)
 */
export interface StatusConfig {
  variant: StatusVariant;
  icon: LucideIcon;
  label: string;
  theme: StatusTheme;
  animation?: StatusAnimation;
}

/**
 * Version permissions structure
 */
export interface VersionPermissions {
  allow_content_mutation?: boolean;
  [key: string]: unknown;
}

/**
 * Default permissions for history versions (typically read-only)
 */
export const DEFAULT_PERMISSIONS: VersionPermissions = {
  allow_content_mutation: false,
};

// Extended History Version used by Timeline Logic (extends DTO with UI overrides)
export interface HistoryVersion extends UnifiedHistoryEntry {
  /**
   * 所属节点的 ID。
   * 使版本对象具备自描述性，无需在父级组件重复传递 nodeId。
   */
  node_id: string;

  /**
   * 逻辑状态覆盖。
   * 用于驱动 UI 状态机（如运行中的动画、等待输入的橙色预警）。
   */
  status_override?: "RUNNING" | "AWAITING_HUMAN_INPUT" | "FAILED";

  /**
   * 是否为实时交互节点。
   * true: 表示该版本是基于 pendingInteraction 虚拟构建的，尚未持久化。
   * false: 表示该版本来自后端历史记录。
   */
  is_live?: boolean;
}

/**
 * Frontend-specific log model for the Smart Console.
 * Unified stream for stdout, stderr, and thoughts.
 */
export interface ExecutionLog {
  id: string;
  timestamp: number;
  type: "stdout" | "stderr" | "thought" | "system";
  content: string;
  attemptIndex?: number; // For associating logs with specific auto-healing attempts
}

/**
 * Represents a node that is currently executing/running.
 */
export interface NodeExecutionState {
  effective_id: string;
  status?: WorkflowStatus;
}
// --- Copilot / AI Assistant Types ---

export type CopilotRole = "user" | "assistant" | "system";

export interface CopilotMessage {
  id: string;
  role: CopilotRole;
  /**
   * The main markdown content to be displayed.
   */
  content: string;
  /**
   * Optional chain-of-thought or reasoning content.
   * This mimics the 'Thought Block' feature from deer-flow-web.
   */
  thought?: string;
  /**
   * Whether the message is currently being streamed/generated.
   */
  isStreaming?: boolean;
  timestamp: number;
}

export interface CopilotSession {
  id: string;
  title: string;
  messages: CopilotMessage[];
  lastUpdated: number;
}

export interface CopilotContextState {
  sessions: CopilotSession[];
  currentSessionId: string | null;
  isStreaming: boolean;
  isLoaded: boolean;
}

// --- Real-time Signaling Types ---

/**
 * Standardized SSE Event Types used for multiplexing.
 */
export type SignalEventType = "message" | "update" | "initial_status" | "error";

/**
 * Represents a business logic event received via the real-time signal channel.
 * Used for broadcasting state changes (e.g. status updates) to UI components.
 */
export interface DomainEvent {
  /**
   * The semantic type of the event.
   * - "update": State change notification.
   * - "initial_status": Connection establishment snapshot.
   */
  type: "update" | "initial_status";

  /**
   * The parsed data payload (e.g. ProjectStatusResponse).
   */
  payload: any;

  /**
   * Contextual Project ID associated with this event.
   */
  projectId?: string;

  /**
   * Client-side timestamp.
   */
  timestamp: number;
}
