"use client";

import { useState, useRef } from "react";
import TextareaAutosize from "react-textarea-autosize";
import { ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface CopilotInputProps {
  onSend: (message: string) => void;
  isStreaming?: boolean;
  onStop?: () => void;
}

export function CopilotInput({ onSend, isStreaming, onStop }: CopilotInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (!value.trim() || isStreaming) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    // [FIX] 添加 pb-[env(safe-area-inset-bottom)] 适配 iPhone 底部
    // [FIX] 增加 pb-2 给底部留一点额外呼吸空间
    <div className="p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] border-t border-slate-200 bg-white shrink-0 relative z-20">
      <div className="relative bg-slate-50 border border-slate-200 rounded-2xl shadow-sm transition-all duration-200 focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-400 focus-within:bg-white focus-within:shadow-md">
        <TextareaAutosize
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything..."
          className="w-full bg-transparent border-none resize-none outline-none px-4 py-3 pr-12 text-sm text-slate-800 placeholder:text-slate-400 max-h-[200px]"
          minRows={1}
          maxRows={8}
        />

        <div className="absolute bottom-2 right-2">
          {isStreaming ? (
            <button
              onClick={onStop}
              className="p-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors flex items-center gap-1.5 px-3 border border-red-200 shadow-sm"
              title="Stop generating"
            >
              <span className="text-[10px] font-bold uppercase tracking-wider">Stop</span>
              <div className="w-2 h-2 bg-red-500 rounded-sm animate-pulse" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!value.trim()}
              className={cn(
                "p-1.5 rounded-lg transition-all duration-200",
                value.trim()
                  ? "bg-black text-white hover:bg-slate-800 shadow-sm"
                  : "bg-slate-200 text-slate-400 cursor-not-allowed",
              )}
              aria-label="Send Message"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
