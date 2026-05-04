"use client";

import React, { useMemo, useState } from "react";
import { ContentBlock, RenderAction } from "@/app/api/schemas";
import { BlockRenderer } from "@/app/components/renderer/BlockRenderer";
import { extractArtifactsFromABP, getCodeBlock, getLogBlocks } from "@/app/lib/abp-utils";
import { buildExecutionLogs } from "@/app/components/renderer/utils/logParsing";
import { LayoutProvider } from "@/app/context/LayoutContext";
import { ScaSelectionProvider } from "@/app/components/renderer/utils/sca-selection-context";
import { SmartConsole } from "@/app/components/stage/atoms/SmartConsole";
import { ArtifactGallery } from "@/app/components/stage/atoms/ArtifactGallery";
import { Group, Panel, useDefaultLayout } from "react-resizable-panels";
import { ResizeHandle } from "@/app/components/layout/ResizableHandle";
import { useMediaQuery } from "@/app/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import { Terminal, Box, FileOutput } from "lucide-react";
import { clientLayoutStorage } from "@/lib/layoutStorage";
import { ExecutionLog } from "@/app/types";

interface ExecutorLayoutProps {
   blocks: ContentBlock[];
   isReadOnly: boolean;
   onAction: (a: RenderAction) => void;
   isSubmitting: boolean;
}

export function ExecutorIdeLayout({ blocks, isReadOnly, onAction, isSubmitting }: ExecutorLayoutProps) {
   const isMobile = useMediaQuery("(max-width: 768px)");
   const [activeTab, setActiveTab] = useState<"output" | "console">("output");
   const [mounted, setMounted] = useState(false);

   React.useEffect(() => setMounted(true), []);

   const { defaultLayout, onLayoutChange } = useDefaultLayout({
      id: "executor-ide-layout",
      storage: clientLayoutStorage,
      panelIds: ["code", "output"],
   });

   // 1. Semantic Slotting Strategy
   const codeBlock = useMemo(() => getCodeBlock({ blocks }), [blocks]);
   const logBlocks = useMemo(() => getLogBlocks({ blocks }), [blocks]);
   const artifacts = useMemo(() => extractArtifactsFromABP({ blocks }), [blocks]);

   // [OPTIMIZED] Removed contextBlocks calculation entirely to clean up logic.
   // The top bar (Slot A) is removed, so we no longer need to filter for 'other' blocks.

   // 2. Consolidate logs
   const logs = useMemo(() => {
      return logBlocks.flatMap((block, index) => {
         const content = block.content;

         // Branch A: Structured Logs (Backend V2 ViewAssembler)
         if (Array.isArray(content)) {
             return content as ExecutionLog[];
         }

         // Branch B: Unstructured String (Legacy / Fallback)
         const strContent = (typeof content === 'string') 
             ? content 
             : JSON.stringify(content ?? "", null, 2);
             
         const parsedLogs = buildExecutionLogs(strContent);

         // Safety: Ensure ID uniqueness when merging multiple blocks
         if (logBlocks.length > 1) {
             return parsedLogs.map(entry => ({
                 ...entry,
                 id: `${block.id || index}-${entry.id}`
             }));
         }

         return parsedLogs;
      });
   }, [logBlocks]);

   React.useEffect(() => {
      const hasError = logs.some(l => l.type === 'stderr');
      if (hasError && artifacts.length === 0) {
         setActiveTab("console");
      }
   }, [logs, artifacts.length]);

   // [FIX] Layout Constant for Dock Overlap
   const DOCK_PADDING = 80;

   return (
      <ScaSelectionProvider scaKey="executor-layout" hasOptions={false} isReadOnly={isReadOnly}>
         {/* 
            [FIX] Immersive Layout Mode:
            - isFixed=true enables Monaco to take 100% height.
            - contentBottomPadding propagates to inner atoms to reserve scroll space.
         */}
         <LayoutProvider isFixed={true} contentBottomPadding={DOCK_PADDING}>
            <div className="h-full w-full flex flex-col bg-slate-50/50 overflow-hidden relative">

               {/* [CRITICAL FIX] REMOVED Slot A: Context Zone.
                   This removes the top bar that was causing layout shifts and displaying unwanted blocks.
                   The main workspace now starts immediately at the top.
               */}

               {/* Slot B & C: Main Workspace */}
               <div className="flex-1 min-h-0 relative">
                  {!mounted ? null : (
                     <Group
                        className="h-full"
                        orientation={isMobile ? "vertical" : "horizontal"}
                        defaultLayout={defaultLayout}
                        onLayoutChange={onLayoutChange}
                     >

                        {/* Left Panel: Code Editor */}
                        <Panel id="code" defaultSize={60} minSize={20} className="flex flex-col bg-white">
                           <div className="h-full w-full flex flex-col border-r border-slate-200">
                              {codeBlock ? (
                                 <BlockRenderer block={codeBlock} onAction={onAction} isReadOnly={isReadOnly} isSubmitting={isSubmitting} />
                              ) : (
                                 <div className="flex-1 flex flex-col items-center justify-center text-slate-300">
                                    <Box className="w-12 h-12 mb-2 opacity-50" />
                                    <span className="text-xs font-medium">No Source Code Available</span>
                                 </div>
                              )}
                           </div>
                        </Panel>

                        <ResizeHandle className="bg-slate-100" />

                        {/* Right Panel: Output & Console */}
                        <Panel id="output" defaultSize={40} minSize={20} className="flex flex-col bg-slate-50">
                           <div className="flex flex-col h-full w-full min-w-0">
                              {/* Tab Header */}
                              <div className="flex items-center border-b border-slate-200 bg-white px-2 shrink-0 h-10 gap-1">
                                 <button
                                    onClick={() => setActiveTab("output")}
                                    className={cn(
                                       "flex items-center gap-2 px-3 h-full border-b-2 text-xs font-bold transition-all",
                                       activeTab === "output"
                                          ? "border-blue-500 text-slate-800 bg-blue-50/20"
                                          : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                                    )}
                                 >
                                    <FileOutput className="w-3.5 h-3.5" />
                                    Artifacts
                                    {artifacts.length > 0 && <span className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded-full text-[9px] border border-slate-200">{artifacts.length}</span>}
                                 </button>
                                 <button
                                    onClick={() => setActiveTab("console")}
                                    className={cn(
                                       "flex items-center gap-2 px-3 h-full border-b-2 text-xs font-bold transition-all",
                                       activeTab === "console"
                                          ? "border-purple-500 text-slate-800 bg-purple-50/20"
                                          : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                                    )}
                                 >
                                    <Terminal className="w-3.5 h-3.5" />
                                    Console
                                    {logs.some(l => l.type === "stderr") && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse ml-1" />}
                                 </button>
                              </div>

                              {/* Tab Content */}
                              <div className="flex-1 overflow-hidden relative">
                                 {/* Content: Artifacts */}
                                 <div
                                    className={cn("absolute inset-0 overflow-y-auto custom-scrollbar p-4 transition-opacity duration-200 pb-24", activeTab === "output" ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none")}
                                 >
                                    {artifacts.length > 0 ? (
                                       <ArtifactGallery artifacts={artifacts} />
                                    ) : (
                                       <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-3 pb-20">
                                          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
                                             <Box className="w-8 h-8 text-slate-300" />
                                          </div>
                                          <div className="text-center">
                                             <p className="text-sm font-bold text-slate-500">No Artifacts Generated</p>
                                             <p className="text-xs text-slate-400 mt-1 max-w-[200px]">Run the code to generate files, images, or data outputs.</p>
                                          </div>
                                       </div>
                                    )}
                                 </div>

                                 {/* Content: Console */}
                                 <div className={cn("absolute inset-0 bg-slate-900 transition-opacity duration-200", activeTab === "console" ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none")}>
                                    <SmartConsole logs={logs} className="border-none rounded-none h-full" paddingBottom={DOCK_PADDING} />
                                 </div>
                              </div>
                           </div>
                        </Panel>
                     </Group>
                  )}
               </div>
            </div>
         </LayoutProvider>
      </ScaSelectionProvider>
   );
}
