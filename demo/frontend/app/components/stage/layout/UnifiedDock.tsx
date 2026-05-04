"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { History, ChevronUp, ChevronDown, Loader2, AlertCircle } from "lucide-react";
import { useDockStore } from "@/lib/stores";
import { AnimatePresence, motion } from "framer-motion";
import { DockTimelinePanel } from "./DockTimelinePanel";
import { useStageStore } from "@/lib/stores";
import { useUI } from "@/app/hooks/useUI";
import { ActionType } from "@/app/api/enums";
import { HistoryVersion } from "@/app/types";

// [FIX] Props updated to accept timeline context
interface UnifiedDockProps {
  projectId: string;
  nodeId: string; // [FIX] Added
  timeline: HistoryVersion[];
  version: HistoryVersion;
  nodeState?: any;
  isActiveVersion?: boolean;
  onRefresh: () => void;
  onAction: (action: any, payload?: any) => void;
  pendingActionId: string | null;
}

export function UnifiedDock({ timeline, version, projectId, nodeId, nodeState, isActiveVersion, onRefresh, onAction, pendingActionId }: UnifiedDockProps) {
  // [FIX] Read actions from Global Store (populated by useDockActions)
  const {
    rightActions, centerContent,
    isInputMode, inputValue, setInputValue, exitInputMode, inputPlaceholder
  } = useDockStore();

  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const dockRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { dialog } = useUI();

  // Close timeline on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dockRef.current && !dockRef.current.contains(event.target as Node)) {
        setIsTimelineOpen(false);
      }
    };
    if (isTimelineOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isTimelineOpen]);

  // Focus input
  useEffect(() => {
    if (isInputMode && inputRef.current) inputRef.current.focus();
  }, [isInputMode]);

  // Helper to handle actions from store (which are wrappers)
  // Store actions already have onClick attached by useDockActions, so we just render them.

  if (!version) return null;

  return (
    <div className="absolute bottom-0 left-0 right-0 z-[100] flex justify-center pointer-events-none px-4" style={{ paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))' }}>
      <div
        ref={dockRef}
        className="w-full max-w-5xl bg-white/95 backdrop-blur-xl border-t border-l border-r border-slate-200 border-b-0 shadow-[0_8px_30px_rgb(0,0,0,0.12)] rounded-t-2xl rounded-b-none flex items-center justify-between p-2 pointer-events-auto relative transition-all duration-300 ease-out ring-1 ring-black/5"
        style={{ height: '68px' }}
      >

        {/* --- ZONE 1: Timeline Anchor --- */}
        <div className="flex items-center gap-2 min-w-[140px] pl-2 relative z-20">
          <button
            onClick={() => setIsTimelineOpen(!isTimelineOpen)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all border select-none",
              isTimelineOpen
                ? "bg-slate-100 border-slate-300 text-slate-900"
                : "bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:shadow-sm"
            )}
          >
            <span className="font-mono">v{String(version.version_index)}</span>
            {isTimelineOpen ? <ChevronDown className="w-3.5 h-3.5 opacity-50" /> : <ChevronUp className="w-3.5 h-3.5 opacity-50" />}
          </button>

          <AnimatePresence>
            {isTimelineOpen && (
              <DockTimelinePanel
                timeline={timeline}
                version={version}
                projectId={projectId}
                nodeId={nodeId} // [FIX] Passed down
                nodeState={nodeState}
                isActiveVersion={isActiveVersion}
                onRefresh={onRefresh}
              />
            )}
          </AnimatePresence>
        </div>

        {/* --- ZONE 2: Context / Status --- */}
        <div className="flex-1 flex items-center justify-center px-4 min-w-0 z-10">
          <AnimatePresence mode="wait">
            {isInputMode ? (
              <motion.div
                key="input"
                initial={{ opacity: 0, scale: 0.95, y: 5 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 5 }}
                className="w-full max-w-md relative"
              >
                <input
                  ref={inputRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder={inputPlaceholder}
                  className="w-full bg-slate-100 border-transparent focus:bg-white focus:border-blue-400 focus:ring-4 focus:ring-blue-500/10 rounded-xl px-4 py-2 text-sm outline-none transition-all placeholder:text-slate-400 font-medium text-slate-800 shadow-inner"
                  onKeyDown={(e) => e.key === "Escape" && exitInputMode()}
                />
              </motion.div>
            ) : (
              <motion.div
                key="content"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="w-full flex justify-center"
              >
                {centerContent || (
                  <span className="text-xs font-medium text-slate-400 select-none opacity-50">
                    Ready
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* --- ZONE 3: Actions --- */}
        <div className="flex items-center gap-2 min-w-fit pl-2 z-20">
          {rightActions.map((action) => {
            const Icon = action.icon;
            // Determine loading state specifically for this action
            const isLoading = action.loading || (pendingActionId === action.id);

            return (
              <button
                key={action.id}
                onClick={action.onClick}
                disabled={action.disabled || isLoading || !!pendingActionId}
                title={action.tooltip}
                className={cn(
                  "h-10 px-5 rounded-xl text-sm font-bold flex items-center gap-2 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-sm select-none whitespace-nowrap",
                  action.variant === "primary" ? "bg-slate-900 text-white hover:bg-black hover:shadow-md border border-transparent" :
                    action.variant === "danger" ? "bg-white text-red-600 border border-red-200 hover:bg-red-50 hover:border-red-300" :
                      action.variant === "ghost" ? "bg-transparent text-slate-500 hover:bg-slate-100 border-transparent shadow-none" :
                        "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300"
                )}
              >
                {isLoading ? (
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-pulse" />
                ) : Icon ? (
                  <Icon className="w-4 h-4" />
                ) : null}
                {action.label}
              </button>
            );
          })}
        </div>

      </div>
    </div>
  );
}
