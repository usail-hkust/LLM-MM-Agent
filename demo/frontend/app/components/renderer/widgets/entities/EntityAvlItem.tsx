"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { CheckCircle, Circle, AlertCircle } from "lucide-react";
import { RenderAtomProps } from "@/app/types";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";

export const EntityAvlItem: React.FC<RenderAtomProps> = (props) => {
  const { block, state } = props;
  const meta = block.meta || {};
  const item = (typeof block.content === 'object' && block.content !== null && !Array.isArray(block.content)) 
    ? block.content as Record<string, any>
    : {}; 
  const readOnly = state.read_only;
  
  // 使用 Hook 获取绑定状态
  const { value, onChange, isReadOnly } = useAtomBinding<boolean>(props);
  
  // Isomorphic state check
  const isChecked = state.data_key ? !!value : meta?.isChecked;

  // Safe Display Values
  const displayIssue = item.issue || "No issue text available";
  const displaySuggestion = item.suggestion || "No suggestion available";

  const handleToggle = () => {
    if (!isReadOnly && state.data_key) {
      onChange(!isChecked);
    }
  };

  return (
    <div
      onClick={handleToggle}
      className={cn(
        "flex gap-3 items-start p-4 rounded-lg border transition-all select-none group",
        readOnly ? "cursor-default opacity-90 bg-slate-50/50" : "cursor-pointer hover:bg-slate-50 hover:border-slate-300",
        isChecked ? "bg-purple-50/30 border-purple-300 ring-1 ring-purple-100" : "bg-white border-slate-200"
      )}
    >
      <div className={cn(
          "mt-0.5 shrink-0 transition-all duration-200", 
          isChecked ? "text-purple-600 scale-110" : "text-slate-300 group-hover:text-slate-400"
      )}>
        {isChecked ? <CheckCircle className="w-5 h-5" /> : <Circle className="w-5 h-5" />}
      </div>

      <div className="flex-1 min-w-0">
        <div className={cn("text-sm font-bold mb-1 leading-tight", isChecked ? "text-purple-900" : "text-slate-800")}>
            {displayIssue}
        </div>
        <div className="text-xs text-slate-500 leading-relaxed">
            {displaySuggestion}
        </div>
        {!item.issue && (
            <div className="text-[10px] text-red-400 flex items-center gap-1 mt-1">
                <AlertCircle className="w-3 h-3" /> Malformed Data
            </div>
        )}
      </div>
    </div>
  );
};
