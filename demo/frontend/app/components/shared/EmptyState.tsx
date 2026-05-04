"use client";

import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        // [FIX] ensure h-full and min-h-0 for flex containers
        "flex flex-col items-center justify-center h-full min-h-0 w-full p-8 text-center animate-fade-in-up select-none",
        className,
      )}
    >
      <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mb-4 border border-slate-100 shadow-sm">
        <Icon className="w-8 h-8 text-slate-300" />
      </div>
      <h3 className="text-sm font-bold text-slate-700 mb-1">{title}</h3>
      {description && <p className="text-xs text-slate-500 max-w-xs leading-relaxed">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

// [FIX] Agent 工作进展显示组件 - 移除旋转的大圆圈，使用文本和进度条
interface AgentProgressProps {
  title?: string;
  description?: string;
  progress?: number;
  message?: string;
  className?: string;
}

export function AgentProgress({ 
  title = "Agent Working...", 
  description, 
  progress = 0, 
  message,
  className 
}: AgentProgressProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center h-full min-h-0 w-full p-8 text-center animate-fade-in-up",
        className,
      )}
    >
      {/* 标题 */}
      <h3 className="text-sm font-bold text-slate-700 mb-2">{title}</h3>
      
      {/* 进度条 */}
      {progress > 0 && (
        <div className="w-48 bg-slate-100 rounded-full h-1.5 mb-3 overflow-hidden">
          <div 
            className="bg-blue-500 h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      
      {/* 当前步骤消息 */}
      {message && (
        <p className="text-xs text-slate-500 max-w-xs leading-relaxed animate-pulse">
          {message}
        </p>
      )}
      
      {/* 描述 */}
      {description && !message && (
        <p className="text-xs text-slate-500 max-w-xs leading-relaxed">{description}</p>
      )}
    </div>
  );
}
