"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronRight, Brain, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";

interface ThoughtBlockProps {
  content: string;
  isStreaming: boolean;
  isCollapsed?: boolean;
}

export function ThoughtBlock({ content, isStreaming }: ThoughtBlockProps) {
  // 默认展开，如果正在流式传输
  const [isUserExpanded, setIsUserExpanded] = useState(isStreaming);
  const [wasAutoExpanded, setWasAutoExpanded] = useState(isStreaming);
  const contentRef = useRef<HTMLDivElement>(null);
  const prevStreamingRef = useRef(isStreaming);
  
  const isOpen = isStreaming || isUserExpanded;
  
  // 当开始流式传输时，自动展开
  useEffect(() => {
    if (isStreaming && !isUserExpanded) {
      setIsUserExpanded(true);
      setWasAutoExpanded(true);
    }
  }, [isStreaming, isUserExpanded]);

  // 思考完成后自动折叠（仅在自动展开的情况下）
  useEffect(() => {
    // 如果从 streaming 变为非 streaming，且是自动展开的，则自动折叠
    if (prevStreamingRef.current && !isStreaming && wasAutoExpanded) {
      setIsUserExpanded(false);
      setWasAutoExpanded(false);
    }
    prevStreamingRef.current = isStreaming;
  }, [isStreaming, wasAutoExpanded]);

  // 处理用户手动切换展开/折叠
  const handleToggle = () => {
    const newExpanded = !isUserExpanded;
    setIsUserExpanded(newExpanded);
    // 用户手动操作时，清除自动展开标记（无论是展开还是折叠）
    setWasAutoExpanded(false);
  };

  // 当内容更新时，自动滚动到底部
  useEffect(() => {
    if (isOpen && contentRef.current && isStreaming) {
      const container = contentRef.current;
      // 使用 requestAnimationFrame 确保 DOM 更新后再滚动
      requestAnimationFrame(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "smooth",
        });
      });
    }
  }, [content, isOpen, isStreaming]);

  // [Fix] Even if content is empty but streaming is true, verify we render the container
  if (!content && !isStreaming) return null;

  return (
    <div className="mb-4 w-full animate-in fade-in slide-in-from-top-1 duration-300">
      <button
        onClick={handleToggle}
        className={cn(
          "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-all duration-200 group select-none",
          isStreaming
            ? "bg-blue-50 border-blue-200 text-blue-700 shadow-sm ring-1 ring-blue-100"
            : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100",
        )}
      >
        <div className={cn("p-1.5 rounded-md transition-colors", isStreaming ? "bg-blue-100 text-blue-600" : "bg-slate-200 text-slate-500")}>
          {isStreaming ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Brain className="w-3.5 h-3.5" />
          )}
        </div>

        <div className="flex-1 flex flex-col leading-none">
            <span className="text-xs font-bold uppercase tracking-wider">
            {isStreaming ? "Thinking Process..." : "Thought Process"}
            </span>
            {isStreaming && <span className="text-[10px] opacity-70 mt-0.5">Generating reasoning...</span>}
        </div>

        {isOpen ? (
          <ChevronDown className="w-4 h-4 opacity-50" />
        ) : (
          <ChevronRight className="w-4 h-4 opacity-50" />
        )}
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div
              ref={contentRef}
              className={cn(
                "p-4 border-x border-b rounded-b-xl text-sm leading-relaxed overflow-x-auto overflow-y-auto custom-scrollbar max-h-[400px]",
                isStreaming
                  ? "bg-blue-50/30 border-blue-200 text-blue-900"
                  : "bg-slate-50 border-slate-200 text-slate-600",
              )}
            >
              {content ? (
                  // 使用通用组件，但这里需要针对 isStreaming 做特殊处理：
                  // ThoughtBlock 的流式光标通常是由 MarkdownDisplay 内部处理比较好，
                  // 但因为 ThoughtBlock 有特殊的背景色和样式，我们通过 className 传递样式
                  <MarkdownDisplay 
                    content={content} 
                    isStreaming={isStreaming} 
                    // 覆盖颜色以匹配 ThoughtBlock 的蓝色主题（如果是 streaming）
                    className={cn(isStreaming && "prose-blue")}
                  />
              ) : (
                  <span className="text-xs italic opacity-50">Initializing thought stream...</span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
