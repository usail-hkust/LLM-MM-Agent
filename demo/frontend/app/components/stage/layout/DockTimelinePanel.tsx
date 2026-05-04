"use client";

import { motion } from "framer-motion";
import { History } from "lucide-react";
import { TimeRail } from "@/app/components/stage/TimeRail";
import { ArtifactRail } from "@/app/components/stage/ArtifactRail";
import { ControlDeck } from "@/app/components/stage/ControlDeck";
import type { HistoryVersion } from "@/app/types";
import { NodeExecutionState } from "@/app/types";

interface DockTimelinePanelProps {
  timeline: HistoryVersion[];
  version: HistoryVersion;
  projectId: string;
  nodeId: string; // [FIX] Added
  nodeState?: NodeExecutionState;
  isActiveVersion?: boolean;
  onRefresh: () => void;
}

export function DockTimelinePanel({ 
  timeline, 
  version, 
  projectId, 
  nodeId, // [FIX] Destructured
  nodeState, 
  isActiveVersion,
  onRefresh 
}: DockTimelinePanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2, ease: "backOut" }}
      className="absolute bottom-[calc(100%+12px)] left-0 w-[600px] bg-white rounded-2xl border border-slate-200 shadow-2xl overflow-hidden flex flex-col max-h-[500px] origin-bottom-left"
    >
      <div className="p-3 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <History className="w-3 h-3" /> Execution History
          </span>
          {nodeState && (
             <div className="scale-90 origin-right">
                <ControlDeck 
                    projectId={projectId} 
                    nodeId={nodeId} // [FIX] Passed explicit ID
                    nodeState={nodeState} 
                    effectiveVersionIndex={version.version_index} 
                    isActiveVersion={isActiveVersion}
                    onRefresh={onRefresh} 
                />
             </div>
          )}
      </div>
      
      <div className="h-16 border-b border-slate-100 bg-white shrink-0">
         <TimeRail timeline={timeline} />
      </div>
      
      <div className="flex-1 overflow-hidden bg-slate-50/50">
         <ArtifactRail version={version} embedded={true} />
      </div>
    </motion.div>
  );
}
