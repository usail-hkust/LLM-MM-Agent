"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Terminal, Brain, AlertCircle, ChevronDown, ChevronRight, ArrowDown, Cpu } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { ExecutionLog } from "@/app/types";

interface SmartConsoleProps {
  logs: ExecutionLog[];
  className?: string;
  // [NEW] Support padding injection
  paddingBottom?: number;
}

export function SmartConsole({ logs, className, paddingBottom = 16 }: SmartConsoleProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [isDark, setIsDark] = useState(true);

  // Helper for safe logs
  const safeLogs = Array.isArray(logs) ? logs : [];

  const lastLog = safeLogs.length > 0 ? safeLogs[safeLogs.length - 1] : null;
  const lastLogId = lastLog?.id ?? null;
  const lastLogContentLength = lastLog?.content?.length ?? 0;

  useLayoutEffect(() => {
    if (shouldAutoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [
    safeLogs.length,
    lastLogId,
    lastLogContentLength,
    shouldAutoScroll,
  ]);
  
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;
    setShouldAutoScroll(isNearBottom);
  };
  
  const scrollToBottom = () => {
    setShouldAutoScroll(true);
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div
      className={cn(
        "flex flex-col h-full overflow-hidden border rounded-xl shadow-sm transition-colors duration-300",
        className,
        isDark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200",
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between px-4 py-2 border-b text-xs font-bold uppercase tracking-wider shrink-0",
          isDark ? "border-slate-800 bg-slate-950 text-slate-400" : "border-slate-100 bg-slate-50 text-slate-500",
        )}
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4" />
          <span>Execution Log</span>
        </div>
        <button
          onClick={() => setIsDark(!isDark)}
          className="hover:text-blue-500 transition-colors"
          title="Toggle Theme"
        >
          {isDark ? "Light Mode" : "Dark Mode"}
        </button>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 pt-4 space-y-3 font-mono text-xs custom-scrollbar relative"
        // [FIX] Apply dynamic padding-bottom to the scroll container
        style={{ paddingBottom: `${paddingBottom}px` }}
      >
        {safeLogs.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center opacity-30 gap-2 select-none min-h-[200px]">
            <Cpu className={cn("w-12 h-12", isDark ? "text-slate-700" : "text-slate-300")} />
            <span className={cn(isDark ? "text-slate-600" : "text-slate-400")}>Ready to capture logs...</span>
          </div>
        )}

        {safeLogs.map((log) => (
          <LogItem key={log.id} log={log} isDark={isDark} />
        ))}

        <div ref={bottomRef} className="h-px w-full" />
      </div>

      <AnimatePresence>
        {!shouldAutoScroll && (
          <motion.button
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            onClick={scrollToBottom}
            // [FIX] Adjust button position based on padding to ensure visibility above Dock
            className="absolute right-6 z-10 bg-blue-600 text-white p-2 rounded-full shadow-lg hover:bg-blue-700 transition-colors"
            style={{ bottom: `${paddingBottom + 24}px` }}
          >
            <ArrowDown className="w-4 h-4" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

// ... LogItem component stays the same ...
function LogItem({ log, isDark }: { log: ExecutionLog; isDark: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isStderr = log.type === "stderr";
  const isThought = log.type === "thought";
  
  // Safe string conversion
  const safeContent = (typeof log.content === 'string') 
    ? log.content 
    : String(log.content ?? "");

  const lines = safeContent.split("\n");
  const isLong = lines.length > 5;
  const showContent = isExpanded || !isLong ? safeContent : lines.slice(0, 5).join("\n") + "\n... (Click to expand)";

  if (isThought) {
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        className={cn(
          "flex gap-3 p-3 rounded-lg border my-2 items-start group select-text",
          isDark ? "bg-slate-800/50 border-purple-500/30 text-purple-200" : "bg-purple-50 border-purple-200 text-purple-900",
        )}
      >
        <div className={cn("p-1.5 rounded-md mt-0.5 shrink-0", isDark ? "bg-purple-500/20" : "bg-purple-100")}>
          <Brain className="w-3.5 h-3.5 text-purple-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-[10px] uppercase opacity-70 mb-1 tracking-wider">Agent Thought</div>
          <div className="font-sans leading-relaxed whitespace-pre-wrap">{safeContent}</div>
        </div>
      </motion.div>
    );
  }

  if (isStderr) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={cn(
          "flex gap-2 p-2 rounded border border-l-4 items-start cursor-pointer group hover:opacity-100",
          isDark ? "bg-red-950/30 border-red-900/50 border-l-red-500 text-red-200" : "bg-red-50 border-red-100 border-l-red-500 text-red-800",
        )}
        onClick={() => isLong && setIsExpanded(!isExpanded)}
      >
        <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0 opacity-70" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <pre className="whitespace-pre-wrap break-all leading-relaxed">{showContent}</pre>
          {isLong && (
            <div className="text-[10px] opacity-60 mt-1 flex items-center gap-1 font-bold uppercase">
              {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {isExpanded ? "Collapse Traceback" : "Show Full Traceback"}
            </div>
          )}
        </div>
      </motion.div>
    );
  }

  return (
    <div
      className={cn(
        "whitespace-pre-wrap break-all leading-tight pl-2 border-l-2 border-transparent",
        log.type === "system" && "italic opacity-50 pl-0 border-none text-[10px]",
        isDark ? "text-slate-300" : "text-slate-700",
        !isDark && log.type !== "system" && "hover:bg-slate-50 hover:border-slate-200 transition-colors",
      )}
    >
      {log.type === "system" && <span className="mr-2">System:</span>}
      {safeContent}
    </div>
  );
}
