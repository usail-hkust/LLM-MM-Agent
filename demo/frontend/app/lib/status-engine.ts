import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Circle,
  Clock,
  RefreshCw,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { StatusConfig, StatusVariant, StatusTheme } from "@/app/types";

/**
 * 视觉主题静态映射表
 */
const THEME_MAP: Record<StatusVariant, StatusTheme> = {
  running: {
    text: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-200",
    dot: "bg-blue-500",
    ring: "ring-blue-100",
  },
  pending: {
    text: "text-orange-700",
    bg: "bg-orange-50",
    border: "border-orange-200",
    dot: "bg-orange-500",
    ring: "ring-orange-100",
  },
  success: {
    text: "text-emerald-700",
    bg: "bg-emerald-50/50",
    border: "border-emerald-200",
    dot: "bg-emerald-500",
    ring: "ring-emerald-100",
  },
  error: {
    text: "text-red-700",
    bg: "bg-red-50/50",
    border: "border-red-200",
    dot: "bg-red-500",
    ring: "ring-red-100",
  },
  warning: {
    text: "text-amber-700",
    bg: "bg-amber-50/50",
    border: "border-amber-200",
    dot: "bg-amber-500",
    ring: "ring-amber-100",
  },
  idle: {
    text: "text-slate-500",
    bg: "bg-slate-50",
    border: "border-slate-200",
    dot: "bg-slate-400",
    ring: "ring-slate-100",
  },
  default: {
    text: "text-slate-600",
    bg: "bg-white",
    border: "border-slate-200",
    dot: "bg-slate-300",
    ring: "ring-slate-100",
  },
};

interface ResolverParams {
  status?: string;
  statusOverride?: "RUNNING" | "AWAITING_HUMAN_INPUT" | "FAILED";
  isPendingAction?: boolean;
  actorType?: "bot" | "user";
}

/**
 * 状态识别引擎 (Pure Logic)
 * 增加对更多后端状态字符串的覆盖
 */
export function resolveStatusIdentity({
  status,
  statusOverride,
  isPendingAction,
  actorType = "bot",
}: ResolverParams): StatusConfig {
  let variant: StatusVariant = "default";
  let icon: LucideIcon = actorType === "user" ? User : Bot;
  let label = "Idle";
  let animate: StatusConfig["animation"] = undefined;

  const s = (statusOverride || status || "").toUpperCase();

  // 1. 优先级最高：强制性运行/等待状态 (通常来自前端交互)
  if (s === "RUNNING" || s === "PROCESSING" || s === "DRAFTING") {
    variant = "running";
    icon = RefreshCw;
    label = "Agent Working...";
    animate = { type: "spin", className: "animate-spin" };
  } else if (
    s === "AWAITING_HUMAN_INPUT" ||
    isPendingAction ||
    s === "REVIEWING"
  ) {
    variant = "pending";
    icon = AlertCircle;
    label = "Awaiting Input";
    animate = { type: "pulse", className: "animate-pulse" };
  }

  // 2. 优先级二：基础生命周期状态
  else {
    switch (s) {
      case "COMMITTED":
      case "COMPLETED":
      case "SUCCESS":
        variant = "success";
        icon = CheckCircle2;
        label = "Completed";
        break;
      case "FAILED":
      case "ERROR":
      case "TERMINATED":
        variant = "error";
        icon = AlertTriangle;
        label = "Failed";
        break;
      case "OBSOLETE":
        variant = "idle";
        icon = Circle;
        label = "Obsolete";
        break;
      case "IDLE":
      case "CREATED":
      case "VOID":
        variant = "idle";
        icon = Circle;
        label = "Created";
        break;
      default:
        variant = "default";
        label = status || "Snapshot";
    }
  }

  return {
    variant,
    icon,
    label,
    theme: THEME_MAP[variant],
    animation: animate,
  };
}
