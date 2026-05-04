"use client";

import { useEffect, useRef } from "react";
import { Box } from "lucide-react";
import { useCopilot } from "@/app/context/CopilotContext";
import { useCopilotChat } from "@/app/hooks/useCopilotChat";
import { MessageItem } from "./MessageItem";

export function MessageList() {
  const { messages, isStreaming } = useCopilot();
  const { sendMessage } = useCopilotChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isStreaming && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    const suggestions = ["Fix the current error", "Explain this workflow", "Generate Python code"];
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
        <div className="w-16 h-16 bg-gradient-to-br from-white to-slate-50 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-center mb-6 relative overflow-hidden group">
          <Box className="w-8 h-8 opacity-20 group-hover:scale-110 transition-transform duration-500" />
          <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/40 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
        </div>
        <h3 className="font-bold text-slate-700 mb-2">AI Copilot Ready</h3>
        <p className="text-xs max-w-[240px] leading-relaxed text-slate-500">
          I can help you analyze nodes, explain errors, or draft configurations.
        </p>

        <div className="mt-8 flex flex-wrap justify-center gap-2 max-w-[280px]">
          {suggestions.map((text) => (
            <button
              key={text}
              className="text-[10px] px-3 py-1.5 bg-white border border-slate-200 rounded-full hover:border-blue-300 hover:text-blue-600 hover:shadow-sm transition-all cursor-pointer"
              onClick={() => {
                if (!isStreaming) sendMessage(text);
              }}
            >
              {text}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-6">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} className="h-1" />
    </div>
  );
}
