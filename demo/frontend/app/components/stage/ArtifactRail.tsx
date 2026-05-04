"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { 
  Layers, 
  CheckCircle, 
  ArrowRight, 
  Files,
  ChevronUp,
  ChevronDown
} from "lucide-react";
import { useStageStore } from "@/lib/stores";
import { HistoryVersion } from "@/app/types";
import { useArtifactGrouping } from "@/app/hooks/useArtifactGrouping"; // [NEW IMPORT]

interface ArtifactRailProps {
  version: HistoryVersion;
  /**
   * [NEW] If true, renders in "headless" mode for embedding inside UnifiedDock.
   * Disables internal header, borders, and forced heights.
   */
  embedded?: boolean;
}

export function ArtifactRail({ version, embedded = false }: ArtifactRailProps) {
  const { selectedArtifactId, selectArtifact } = useStageStore();
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  // Mobile auto-collapse logic
  useEffect(() => { 
    if (!embedded && window.innerWidth < 640) setIsCollapsed(true); 
  }, [embedded]);

  // [REFACTORED]: Use the new hook
  const timelineNodes = useArtifactGrouping(version);

  const activeId = selectedArtifactId || "FINAL_OUTPUT";

  if (timelineNodes.length <= 1) return null;

  const containerClasses = embedded 
    ? "bg-white flex flex-col h-full" 
    : cn(
        "bg-white border-t border-slate-200 flex flex-col shrink-0 z-30 shadow-[0_-4px_12px_-4px_rgba(0,0,0,0.05)] animate-enter transition-all duration-300",
        isCollapsed ? "h-10" : "h-40"
      );

  return (
    <div className={containerClasses}>
      {/* Header - Only render if NOT embedded */}
      {!embedded && (
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="px-4 py-2 bg-slate-50 border-b border-slate-100 flex justify-between items-center shrink-0 hover:bg-slate-100 transition-colors"
        >
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-3 h-3" /> Execution Timeline
          </span>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-slate-400 font-mono">
              {version.artifacts?.length || 0} Artifacts
            </span>
            <span className="w-px h-3 bg-slate-300/50"></span>
            <span className="text-[10px] text-slate-400 font-mono">
              {timelineNodes.length} Steps
            </span>
            {isCollapsed ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </div>
        </button>
      )}

      {/* Scroll Area */}
      <div className={cn(
        "flex-1 overflow-x-auto flex items-center px-4 py-3 gap-3 custom-scrollbar transition-opacity duration-300",
        // If embedded, always visible. If standalone, respect isCollapsed.
        !embedded && isCollapsed ? "opacity-0 pointer-events-none h-0" : "opacity-100"
      )}>
        {timelineNodes.map((node, idx) => {
          const { primaryArtifact, roundIndex, type, subCountLabel, icon: Icon } = node;
          
          const isPrimarySelected = activeId === primaryArtifact.id;
          const isSubSelected = node.subArtifacts.some(sub => sub.id === activeId);
          const isSelected = isPrimarySelected || isSubSelected;

          const isFinal = type === "FINAL";
          const hasPrev = idx > 0;

          return (
            <div key={`${primaryArtifact.id}-${idx}`} className="flex items-center h-full relative group/wrapper">
              
              {/* Connector Arrow */}
              {hasPrev && (
                <div className="flex items-center justify-center w-6 opacity-30">
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                </div>
              )}

              <button
                onClick={() => selectArtifact(isFinal ? null : primaryArtifact.id)}
                className={cn(
                  // FIX 3: 
                  // w-44: 稍微加宽，防止文字换行
                  // py-3.5: 关键点！增加垂直内边距，确保 justify-between 推开的元素离边缘有距离，不会被圆角切掉
                  "flex flex-col text-left justify-between shrink-0 w-44 h-full px-4 py-3.5 rounded-xl border transition-all duration-200 relative group overflow-hidden",
                  isSelected
                    ? "bg-slate-800 border-slate-800 ring-2 ring-slate-200 text-white shadow-xl transform -translate-y-1"
                    : "bg-white border-slate-200 hover:border-blue-300 hover:shadow-md text-slate-600 hover:-translate-y-0.5",
                )}
              >
                {!isFinal && subCountLabel && (
                    <div className={cn(
                        "absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-white/10 to-transparent opacity-20 pointer-events-none transition-opacity",
                        isSelected ? "from-white/20 opacity-30" : "from-black/5"
                    )}>
                        <Files className="absolute top-3 right-3 w-10 h-10 opacity-20" />
                    </div>
                )}

                {/* Top Section: Round Tag */}
                <div className="flex justify-between items-center w-full">
                  <span
                    className={cn(
                      "text-[9px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wide shadow-sm",
                      isSelected
                        ? "bg-white/20 text-white border border-white/10"
                        : isFinal
                          ? "bg-emerald-50 text-emerald-600 border border-emerald-100"
                          : "bg-slate-100 text-slate-500 border border-slate-200",
                    )}
                  >
                    {isFinal ? "Final" : `Round ${roundIndex}`}
                  </span>
                  {isSelected && <CheckCircle className="w-4 h-4 text-emerald-400 animate-in fade-in zoom-in duration-200" />}
                </div>

                {/* Middle Section: Main Label */}
                {/* 增加 pt-1 稍微拉开一点和顶部的距离 */}
                <div className="flex flex-col gap-1 mt-1">
                   <div className="flex items-center gap-2">
                        <Icon className={cn("w-4 h-4", isSelected ? "text-blue-200" : isFinal ? "text-emerald-500" : "text-blue-500")} />
                        <span className={cn("text-sm font-bold truncate", isSelected ? "text-white" : "text-slate-800")}>
                            {node.label}
                        </span>
                   </div>
                   {!subCountLabel && (
                      <span className={cn("text-[10px] truncate w-full opacity-70 pl-6", isSelected ? "text-slate-300" : "text-slate-400")}>
                          {primaryArtifact.summary || "Processing..."}
                      </span>
                   )}
                </div>

                {/* Bottom Section: Sub-count Badge */}
                <div className="flex flex-col w-full mt-1">
                  {subCountLabel ? (
                     <div className={cn(
                        "flex items-center gap-1.5 text-[10px] font-medium w-fit px-2.5 py-1 rounded-full transition-colors",
                        isSelected ? "bg-blue-500/40 text-blue-50 border border-blue-400/30" : "bg-blue-50 text-blue-600 border border-blue-100"
                     )}>
                        <span className={cn("w-1.5 h-1.5 rounded-full", isSelected ? "bg-blue-200" : "bg-blue-500")}></span>
                        {subCountLabel}
                     </div>
                  ) : (
                    // 占位符，保持对齐
                    <div className="h-5" /> 
                  )}
                </div>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}