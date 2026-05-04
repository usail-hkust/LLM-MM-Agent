"use client";

import { memo, useState } from "react";
import { CopilotMessage } from "@/app/context/CopilotContext";
import { User, Bot, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { ThoughtBlock } from "./ThoughtBlock";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";

export const MessageItem = memo(function MessageItem({
  message,
}: {
  message: CopilotMessage;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "flex w-full gap-4 animate-in slide-in-from-bottom-2 fade-in duration-300",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm border",
          isUser
            ? "bg-black text-white border-black"
            : "bg-white text-blue-600 border-slate-200",
        )}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      <div
        className={cn(
          "flex flex-col max-w-full min-w-[200px]",
          isUser ? "items-end" : "items-start",
        )}
      >
        {isUser && (
          <div className="bg-black text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm leading-relaxed shadow-sm whitespace-pre-wrap">
            {message.content}
          </div>
        )}

        {!isUser && (
          <div className="w-full">
            {message.thought !== undefined && (
              <ThoughtBlock
                content={message.thought ?? ""}
                isStreaming={!!message.isStreaming && !message.content}
              />
            )}

            {/* 当有内容或正在流式传输时渲染 */}
            {(message.content || message.isStreaming) && (
              <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm p-5 relative group min-h-[60px]">
                {/* 使用通用组件处理渲染和流式光标 */}
                <MarkdownDisplay
                  content={message.content || ""}
                  isStreaming={message.isStreaming}
                />

                {!message.isStreaming && message.content && (
                  <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={handleCopy}
                      className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                      title="Copy Markdown"
                    >
                      {copied ? (
                        <Check className="w-3.5 h-3.5 text-green-500" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <span className="text-[10px] text-slate-400 mt-1 px-1 font-medium opacity-60">
          {isUser ? "You" : "AI Copilot"} •{" "}
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}, (prev, next) => (
  prev.message.content === next.message.content &&
  prev.message.thought === next.message.thought &&
  prev.message.isStreaming === next.message.isStreaming
));
