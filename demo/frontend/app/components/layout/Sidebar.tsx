"use client";
import { TimelineNode } from "@/app/api/schemas";
import { useStageStore } from "@/lib/stores";
import { useStatusVariant } from "@/app/hooks/useStatusVariant";
import { cn } from "@/lib/utils";
import { LayoutTemplate, GitCommit, Lock } from "lucide-react";
import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";

interface PhaseGroup {
  phase: string;
  nodes: TimelineNode[];
}

export function Sidebar({ nodes, isLoading }: { nodes: TimelineNode[], isLoading?: boolean }) {
  const { selectedNodeId, selectNode } = useStageStore();

  const phases = useMemo(() => {
    if (!nodes) return [];
    const groups: PhaseGroup[] = [];
    const map = new Map<string, number>();

    nodes.forEach((node) => {
      const phaseName = node.phase || "General";
      if (!map.has(phaseName)) {
        map.set(phaseName, groups.length);
        groups.push({ phase: phaseName, nodes: [] });
      }
      groups[map.get(phaseName)!].nodes.push(node);
    });

    return groups;
  }, [nodes]);

  // [FIX] Layout Logic:
  // Removed `w-[280px]` and `shrink-0`.
  // The parent Panel in CopilotLayout controls the width via standard CSS layout.
  // Sidebar should simply fill the available space (`w-full`).
  // Also removed `border-r` as the parent container handles the visual divider/border.
  return (
    <div className="h-full flex flex-col bg-slate-50/50 w-full">
      <div className="h-14 flex items-center px-4 border-b bg-white shrink-0 gap-2 text-slate-700 font-bold text-sm">
        <LayoutTemplate className="w-4 h-4"/> Workflow
      </div>
      
      <div className="flex-1 overflow-y-auto p-3 space-y-6 custom-scrollbar">
        {isLoading ? (
           <div className="space-y-4">
             {[1,2,3].map(i => (
               <div key={i} className="space-y-2">
                 <Skeleton className="h-3 w-16 bg-slate-200/50" />
                 <Skeleton className="h-10 w-full bg-slate-200/50 rounded-lg" />
                 <Skeleton className="h-10 w-full bg-slate-200/50 rounded-lg" />
               </div>
             ))}
           </div>
        ) : (
          phases.map((group) => (
            <div key={group.phase} className="flex flex-col gap-2">
              <div className="flex items-center px-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider select-none">
                {group.phase}
              </div>

              <div className="flex flex-col gap-1">
                {group.nodes.map((node) => (
                  <SidebarItem 
                    key={node.id} 
                    node={node} 
                    isSelected={selectedNodeId === node.id} 
                    onSelect={() => selectNode(node.id)}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SidebarItem({ node, isSelected, onSelect }: { node: TimelineNode, isSelected: boolean, onSelect: () => void }) {
  // Use the central status logic to get colors and animations
  const { icon: Icon, theme, animation, variant } = useStatusVariant({
    status: node.status,
    // Provide hints for interactive states
    isPendingAction: node.status === "DRAFTING" || node.status === "REVIEWING", 
  });

  const isLocked = node.status === "LOCKED";

  return (
    <button
      onClick={() => !isLocked && onSelect()}
      disabled={isLocked}
      className={cn(
        "relative w-full flex items-center gap-3 p-2 rounded-lg text-left transition-all group",
        isSelected 
          ? "bg-white shadow-sm ring-1 ring-slate-200 z-10" 
          : "hover:bg-slate-100/80 hover:shadow-sm",
        isLocked && "opacity-50 cursor-not-allowed grayscale"
      )}
    >
      <div className={cn(
        "w-7 h-7 rounded-md flex items-center justify-center shrink-0 border transition-colors relative",
        isSelected 
          ? cn(theme.bg, theme.border, theme.text) 
          : "bg-white border-slate-200 text-slate-400 group-hover:border-slate-300"
      )}>
        <Icon className={cn("w-3.5 h-3.5", animation?.className)} />
        
        {/* Status Dot for Running/Pending */}
        {(variant === "running" || variant === "pending") && (
           <span className={cn("absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full border border-white", theme.dot)} />
        )}
      </div>
      
      <div className="flex-1 min-w-0">
        <div className={cn(
          "text-xs font-medium truncate transition-colors",
          isSelected ? "text-slate-900" : "text-slate-600 group-hover:text-slate-800"
        )}>
          {node.title}
        </div>
        
        {node.iteration_index > 0 && (
          <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
            <GitCommit className="w-2.5 h-2.5" /> 
            Iteration {node.iteration_index}
          </div>
        )}
      </div>

      {isSelected && (
         <div className="absolute right-2 w-1.5 h-1.5 rounded-full bg-blue-500" />
      )}
      
      {isLocked && <Lock className="absolute right-2 w-3 h-3 text-slate-300" />}
    </button>
  );
}
