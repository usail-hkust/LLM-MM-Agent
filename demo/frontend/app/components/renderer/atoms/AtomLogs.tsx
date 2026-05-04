"use client";

import React from "react";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";
import { ExecutionLog } from "@/app/types";
import { cn } from "@/lib/utils";

interface AtomLogsProps {
  value: string | ExecutionLog[];
  title?: string;
}

export const AtomLogs: React.FC<AtomLogsProps> = ({ value, title }) => {
  const content = Array.isArray(value)
    ? value.map((log) => log.content).join("\n")
    : String(value ?? "");

  return (
    <div className="h-full w-full bg-slate-900 text-slate-100 overflow-hidden flex flex-col rounded-lg">
      {title && (
        <div className="bg-slate-800 text-slate-400 text-xs px-4 py-2 font-bold border-b border-slate-700">
          {title}
        </div>
      )}
      <div className={cn("flex-1 overflow-y-auto custom-scrollbar p-4")}>
        <MarkdownDisplay content={content} className="prose-invert font-mono text-sm" />
      </div>
    </div>
  );
};
