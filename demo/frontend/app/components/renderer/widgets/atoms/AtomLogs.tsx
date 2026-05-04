"use client";

import React from "react";
import { RenderAtomProps, ExecutionLog } from "@/app/types";
import { AtomShell } from "./AtomShell";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";

export const AtomLogs: React.FC<RenderAtomProps> = (props) => {
  return (
    <AtomShell {...props} variant="fill" showCopy>
      {({ value }) => {
        const safeString = (val: any) =>
          (typeof val === "object" && val !== null) ? JSON.stringify(val, null, 2) : String(val ?? "");

        const content = Array.isArray(value)
          ? (value as any[]).map((log) => safeString(log.content)).join("\n")
          : safeString(value);

        return (
          <div className="h-full w-full bg-slate-900 text-slate-100 p-4">
            <MarkdownDisplay content={content} className="prose-invert font-mono text-sm" />
          </div>
        );
      }}
    </AtomShell>
  );
};
