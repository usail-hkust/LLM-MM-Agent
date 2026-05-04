"use client";
import { ContentBlock, RenderAction } from "@/app/api/schemas";
import { BlockRenderer } from "@/app/components/renderer/BlockRenderer";
import { cn } from "@/lib/utils";
import { useMemo } from "react";
import { ScaSelectionProvider } from "@/app/components/renderer/utils/sca-selection-context";
import { LayoutProvider } from "@/app/context/LayoutContext";
import { ExecutorIdeLayout } from "./ExecutorIdeLayout";
import { isBlockVisible } from "@/app/domain/abp";
import { Loader2, Sparkles } from "lucide-react"; // [FIX] Added visual assets

interface LayoutProps {
  blocks: ContentBlock[];
  isReadOnly: boolean;
  onAction: (a: RenderAction) => void;
  isSubmitting: boolean;
  mode: "workbench" | "standard" | "document" | "selection" | "focus" | string;
  nodeType?: string;
  // [FIX] 接收 status 以驱动遮罩
  status?: string;
}

export function UnifiedStageLayout({ blocks, isReadOnly, onAction, isSubmitting, mode, nodeType, status }: LayoutProps) {

  const visibleBlocks = useMemo(() => {
    return blocks.filter(isBlockVisible);
  }, [blocks]);

  const isExecutor = useMemo(() => {
    if (!nodeType) return false;
    const type = nodeType.toUpperCase();
    return type.includes("EXECUTOR") || type.includes("CODE_GENERATOR");
  }, [nodeType]);

  const scaBlocks = useMemo(
    () =>
      visibleBlocks.filter(
        (block) =>
          block.render_type === "SCA_OPTION_CARD" ||
          block.render_type === "SCA_PLAN_CARD",
      ),
    [visibleBlocks],
  );

  const scaKey = useMemo(() => scaBlocks.map((b) => b.id).join("|"), [scaBlocks]);
  const hasScaOptions = scaBlocks.length > 0;
  const enableScaGrid = mode === "standard" && hasScaOptions;

  // [CRITICAL FIX] 状态驱动的忙碌遮罩
  // 如果状态是 DRAFTING/RUNNING，且屏幕上仍有旧内容（Refine场景），则显示遮罩
  const isRefining = (status === 'DRAFTING' || status === 'RUNNING' || status === 'PROCESSING') && visibleBlocks.length > 0;

  // --- Executor Layout Strategy ---
  if (isExecutor && (mode === "standard" || mode === "workbench")) {
    return (
      <div className="relative h-full w-full">
        <ExecutorIdeLayout
          blocks={visibleBlocks}
          isReadOnly={isReadOnly}
          onAction={onAction}
          isSubmitting={isSubmitting}
        />
        {/* Executor 遮罩 */}
        {isRefining && (
          <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-[4px] flex items-center justify-center animate-in fade-in duration-500 pointer-events-auto cursor-wait">
            <div className="bg-white/95 border border-blue-200 shadow-2xl rounded-full px-8 py-4 flex items-center gap-4 ring-8 ring-blue-50/50 animate-in zoom-in-95 duration-300">
              <div className="relative">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                <Sparkles className="w-3 h-3 text-blue-400 absolute -top-1 -right-1 animate-pulse" />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-bold text-slate-900 leading-none">Agent Working</span>
                <span className="text-[10px] font-medium text-slate-500 mt-1">Refining code based on your feedback...</span>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // --- Standard Layout Strategy ---
  const isWorkbench = mode === "workbench";
  // [FIX] 增加 relative 定位，作为遮罩层的锚点
  const scrollerClass = isWorkbench
    ? "h-full w-full overflow-hidden relative"
    : "h-full w-full overflow-y-auto custom-scrollbar relative";

  const layoutClass = {
    workbench: "grid grid-cols-1 lg:grid-cols-2 gap-4 p-4 h-full",
    focus: "max-w-6xl mx-auto w-full p-6 pb-32 space-y-6",
    standard: enableScaGrid
      ? "grid grid-cols-1 lg:grid-cols-2 auto-rows-max gap-6 p-6 pb-32 content-start"
      : "grid grid-cols-1 gap-6 p-6 pb-32 content-start",
    document: "max-w-4xl mx-auto p-8 pb-32 space-y-6",
    selection: "grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 auto-rows-max content-start gap-6 p-6 pb-32"
  }[mode] || "space-y-4 p-4 pb-32";

  return (
    <ScaSelectionProvider scaKey={scaKey} hasOptions={hasScaOptions} isReadOnly={isReadOnly}>
      <LayoutProvider isFixed={isWorkbench}>
        <div className={scrollerClass}>
          <div className={cn("min-w-0 min-h-full relative", layoutClass)}>

            {/* [CRITICAL FIX] 忙碌遮罩层 - 填补视觉空白 */}
            {isRefining && (
              <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-[4px] flex items-start justify-center pt-40 animate-in fade-in duration-500 pointer-events-auto cursor-wait rounded-xl">
                <div className="bg-white border border-blue-200 shadow-2xl rounded-2xl px-8 py-6 flex flex-col items-center gap-4 ring-8 ring-blue-50/50 select-none animate-in slide-in-from-bottom-4 duration-500">
                  <div className="relative flex items-center justify-center w-12 h-12 bg-blue-50 rounded-full">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                    <Sparkles className="w-4 h-4 text-blue-400 absolute -top-1 -right-1 animate-pulse" />
                  </div>
                  <div className="text-center">
                    <h3 className="text-base font-bold text-slate-900">Agent is working</h3>
                    <p className="text-xs font-medium text-slate-500 mt-1 max-w-[200px]">Generating updated content based on your feedback.</p>
                  </div>
                  {/* Subtle Progress Bar Placeholder to make it feel "active" */}
                  <div className="w-full h-1 bg-slate-100 rounded-full overflow-hidden mt-2">
                    <div className="h-full bg-blue-600 w-1/3 animate-[progress_2s_infinite_linear]" style={{ backgroundSize: '200% 100%', backgroundImage: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)' }} />
                  </div>
                </div>
              </div>
            )}

            {visibleBlocks.map((block, index) => {
              const key = `${block.id ?? "block"}-${index}`;
              const isConsole = block.render_type === "LOG_CONSOLE";
              const spanClass = (isWorkbench && isConsole) ? "lg:col-span-2" : "";

              return (
                <div
                  key={key}
                  className={cn(
                    "min-w-0 min-h-0 flex flex-col transition-opacity duration-300",
                    isWorkbench ? "h-full" : "",
                    spanClass,
                    // [Optional] 遮罩下内容变淡
                    isRefining ? "opacity-40 pointer-events-none grayscale-[0.5]" : "opacity-100"
                  )}
                >
                  <BlockRenderer
                    block={block}
                    onAction={onAction}
                    isReadOnly={isReadOnly}
                    isSubmitting={isSubmitting}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </LayoutProvider>
    </ScaSelectionProvider>
  );
}
