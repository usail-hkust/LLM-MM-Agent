"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, PanelRightOpen } from "lucide-react";
import { useMediaQuery } from "@/app/hooks/useMediaQuery";
import { Group, Panel, useDefaultLayout } from "react-resizable-panels";
import { ResizeHandle } from "./ResizableHandle";
import { useCopilotUIStore } from "@/lib/stores/copilot-ui";
import { clientLayoutStorage } from "@/lib/layoutStorage";

interface CopilotLayoutProps {
  sidebar: React.ReactNode;
  stage: React.ReactNode;
  copilot: React.ReactNode;
  isSidebarOpen: boolean;
  onSidebarClose: () => void;
}

export function CopilotLayout({
  sidebar,
  stage,
  copilot,
  isSidebarOpen,
  onSidebarClose,
}: CopilotLayoutProps) {
  const isCopilotOpen = useCopilotUIStore((s) => s.isOpen);
  const togglePanel = useCopilotUIStore((s) => s.toggle);
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => setMounted(true), []);

  const panelIds = [
    isSidebarOpen ? "sidebar" : null,
    "stage",
    isCopilotOpen ? "copilot" : null,
  ].filter((id): id is string => Boolean(id));

  // [FIX] 根据当前面板组合生成唯一的 layout ID
  // 使用 v11 版本强制清除旧的布局缓存（调整默认宽度为 15%）
  const layoutId = `mm-global-layout-v11-${panelIds.join("-")}`;
  
  const { defaultLayout, onLayoutChange } = useDefaultLayout({
    id: layoutId, 
    storage: clientLayoutStorage,
    panelIds,
  });

  // [FIX] Safely clear invalid layout storage
  useEffect(() => {
    if (!mounted) return;
    
    const stored = clientLayoutStorage.getItem(layoutId);
    if (stored) {
      try {
        // Handle empty string specifically to avoid JSON.parse error
        if (stored.trim() === '') {
           clientLayoutStorage.removeItem(layoutId);
           return;
        }

        const parsed = JSON.parse(stored);
        if (parsed && Array.isArray(parsed)) {
          let hasInvalidSize = false;
          if (isSidebarOpen && parsed[0] !== undefined && parsed[0] < 15) hasInvalidSize = true;
          if (isCopilotOpen) {
            const copilotIndex = parsed.length - 1;
            if (parsed[copilotIndex] !== undefined && parsed[copilotIndex] < 15) {
              hasInvalidSize = true;
            }
          }
          if (hasInvalidSize) {
            // [FIX] Use removeItem instead of setting to empty string
            clientLayoutStorage.removeItem(layoutId);
          }
        }
      } catch {
        // [FIX] Use removeItem instead of setting to empty string
        clientLayoutStorage.removeItem(layoutId);
      }
    }
  }, [layoutId, mounted, isSidebarOpen, isCopilotOpen]);

  // --- Mobile View (保持不变) ---
  if (isMobile) {
    return (
      <div className="relative h-[100dvh] w-full overflow-hidden flex flex-col bg-slate-50">
        <AnimatePresence>
          {isSidebarOpen && (
            <>
              <div className="fixed inset-0 bg-black/20 z-40 backdrop-blur-sm" onClick={onSidebarClose} />
              <motion.div
                initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }}
                transition={{ type: "spring", bounce: 0, duration: 0.3 }}
                className="fixed inset-y-0 left-0 z-50 w-[280px] bg-white shadow-2xl border-r border-slate-200"
              >
                {sidebar}
              </motion.div>
            </>
          )}
        </AnimatePresence>
        <div className="flex-1 min-h-0 w-full relative z-0">{stage}</div>
        <AnimatePresence>
          {isCopilotOpen && (
            <motion.div
              initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
              className="fixed inset-0 z-50 bg-white flex flex-col"
            >
              <div className="h-12 border-b flex items-center justify-between px-4 shrink-0 bg-white">
                <span className="font-bold">AI Assistant</span>
                <button onClick={togglePanel}><X className="w-5 h-5" /></button>
              </div>
              <div className="flex-1 min-h-0 relative w-full overflow-hidden">{copilot}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  // --- Desktop View (激进宽版策略) ---
  if (!mounted) return null;

  return (
    <div className="h-screen w-full bg-slate-50 overflow-hidden relative isolate">
      <Group
        className="h-full w-full" 
        orientation="horizontal"
        defaultLayout={defaultLayout}
        onLayoutChange={onLayoutChange}
      >
        {isSidebarOpen && (
          <>
            <Panel
              id="sidebar"
              // [FIX] 侧边栏：使用固定的默认宽度，避免右侧栏关闭时变宽
              // 使用固定的 15%，这样当右侧栏关闭/打开时，左侧栏宽度保持不变
              defaultSize={15}  // 固定 15%，不随右侧栏状态改变
              minSize={15}      // 最小宽度 15%，确保内容可见（180px @ 1200px）
              // 移除 maxSize 限制，允许拉到接近 100%（由于 Stage minSize=0，理论上可以拉到 100%）
              className="bg-white border-r border-slate-200 z-10"
            >
              <div className="h-full w-full overflow-hidden flex flex-col">
                {sidebar}
              </div>
            </Panel>
            <ResizeHandle />
          </>
        )}

        {/* 
           [CORE FIX] 中间区域 Stage
           minSize={0} 是关键。
           这告诉布局引擎："如果用户想把左右拉满，中间可以牺牲到消失"。
           这彻底移除了所有"拉不动"的隐形天花板。
        */}
        <Panel 
            id="stage" 
            minSize={0}
            // [FIX] 中间区域：调整默认宽度，让中间区域更宽
            // 三栏布局时：Sidebar 15% + Stage 70% + Copilot 15% = 100%
            // 两栏布局时（有Sidebar无Copilot）：Sidebar 15% + Stage 85% = 100%
            // 两栏布局时（无Sidebar有Copilot）：Stage 85% + Copilot 15% = 100%
            defaultSize={isSidebarOpen && isCopilotOpen ? 70 : (isSidebarOpen ? 85 : (isCopilotOpen ? 85 : 100))}
            className="bg-slate-50/30 relative z-0"
        >
          <div className="h-full w-full flex flex-col overflow-hidden relative">
            {stage}
            
            {!isCopilotOpen && (
              <button
                onClick={togglePanel}
                className="absolute right-0 top-1/2 -translate-y-1/2 p-2 bg-white border-l border-y border-slate-200 rounded-l-lg shadow-sm text-slate-400 hover:text-blue-600 hover:w-10 w-8 transition-all z-50 flex items-center justify-center group"
                title="Open Copilot"
              >
                <PanelRightOpen className="w-4 h-4 group-hover:scale-110 transition-transform" />
              </button>
            )}
          </div>
        </Panel>

        {isCopilotOpen && (
          <>
            <ResizeHandle />
            <Panel
              id="copilot"
              // [FIX] Copilot：使用固定的默认宽度，避免左侧栏状态改变时变宽
              // 使用固定的 15%，这样当左侧栏关闭/打开时，右侧栏宽度保持不变
              defaultSize={15}  // 固定 15%，不随左侧栏状态改变
              minSize={15}  // 最小宽度 15%，确保内容可见（180px @ 1200px）
              // 移除 maxSize 限制，允许拉到接近 100%（由于 Stage minSize=0，理论上可以拉到 100%）
              className="bg-white border-l border-slate-200 z-10"
            >
               <div className="h-full w-full overflow-hidden flex flex-col">
                 {copilot}
               </div>
            </Panel>
          </>
        )}
      </Group>
    </div>
  );
}
