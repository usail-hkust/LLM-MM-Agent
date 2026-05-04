"use client";

import { cn } from "@/lib/utils";
import { AlertCircle, ArrowRight, History } from "lucide-react";
import { useStageStore } from "@/lib/stores";

export function GlobalBeacon({ pendingNodeId }: { pendingNodeId?: string }) {
  const { selectedNodeId, selectNode, timeTravel, isHead } = useStageStore();

  if (!pendingNodeId) return null;

  const isWrongNode = selectedNodeId !== pendingNodeId;
  const isWrongTime = selectedNodeId === pendingNodeId && !isHead;

  // 如果状态正确（在正确的节点且是最新即时状态），则不需要显示 Banner
  if (!isWrongNode && !isWrongTime) return null;

  const handleAction = () => {
    if (isWrongNode) {
      selectNode(pendingNodeId);
    } else {
      timeTravel(null);
    }
  };

  return (
    <div className="w-full shrink-0 z-20 animate-in slide-in-from-top duration-300 relative overflow-hidden">
      <button
        type="button"
        onClick={handleAction}
        className={cn(
          "w-full px-6 py-3 flex items-center justify-between border-b relative text-left cursor-pointer transition-all",
          "hover:brightness-95 active:scale-[0.997] focus:outline-none focus-visible:ring-2 focus-visible:ring-white/60",
          isWrongNode 
            ? "bg-blue-600 border-blue-700 text-white" 
            : "bg-amber-500 border-amber-600 text-white"
        )}
      >
        {/* 背景纹理 */}
        <div className="absolute inset-0 opacity-10 bg-[url('https://www.transparenttextures.com/patterns/diagonal-stripes.png')] pointer-events-none" />

        <div className="flex items-center gap-4 relative z-10">
          <div className="p-1.5 bg-white/20 rounded-lg backdrop-blur-sm shrink-0">
            {isWrongNode ? <AlertCircle className="w-5 h-5" /> : <History className="w-5 h-5" />}
          </div>

          <div className="flex flex-col leading-none gap-1">
            <span className="font-bold text-sm tracking-wide">
              {isWrongNode ? "Intervention Required" : "Historical View"}
            </span>
            <span className="opacity-90 text-xs font-medium">
              {isWrongNode ? (
                <span>
                  The agent is paused and waiting for input at node{" "}
                  <span className="font-mono font-bold bg-white/20 px-1.5 py-0.5 rounded ml-0.5 border border-white/10">
                    {pendingNodeId}
                  </span>
                </span>
              ) : (
                "You are viewing a past snapshot. Live interactions are disabled."
              )}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider relative z-10">
          {isWrongNode ? "Jump to Node" : "Go to Live"}
          <ArrowRight className="w-3.5 h-3.5" />
        </div>
      </button>
    </div>
  );
}
