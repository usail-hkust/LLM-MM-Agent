"use client";

import React, { useState, useEffect } from "react";
import { RenderAtomProps } from "@/app/types";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";
import { AtomShell } from "./AtomShell";
import { cn } from "@/lib/utils";
import TextareaAutosize from "react-textarea-autosize";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { Edit3, Eye, FileText } from "lucide-react";

// [FIX] Add logs/stdout/stderr to terminal tags
const TERMINAL_TAGS = new Set(["execution_logs", "logs", "stdout", "stderr", "error", "compilation_log"]);

export const AtomText: React.FC<RenderAtomProps> = (props) => {
  const { block, state } = props;
  const isTerminal = block.tags?.some((tag) => TERMINAL_TAGS.has(tag)) ?? false;
  const isMarkdown = isTerminal || block.type === 'MARKDOWN' || (block.meta?.markdown ?? true);

  // Use AtomBinding Hook to manage edit state
  const { value, onChange, isReadOnly } = useAtomBinding<string>(props);
  const [isEditing, setIsEditing] = useState(false);
  const [localValue, setLocalValue] = useState("");

  // Sync local value when entering edit mode or when external value changes
  useEffect(() => {
    const safeVal = value === null || value === undefined ? "" : String(value);
    setLocalValue(safeVal);
  }, [value]);

  const handleEditToggle = () => {
    if (isReadOnly) return;
    setIsEditing(!isEditing);
  };

  const handleBlur = () => {
    // Commit change on blur? 
    // Usually handled by onChange in realtime for autosave hooks
    // but we can ensure consistency here
    if (localValue !== value) {
      onChange(localValue);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setLocalValue(val);
    onChange(val);
  };

  // Header Extra: Toggle Button
  const headerAction = !isReadOnly && !isTerminal && (
    <button
      onClick={handleEditToggle}
      className={cn(
        "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase transition-all select-none border",
        isEditing
          ? "bg-blue-50 text-blue-600 border-blue-200 hover:bg-blue-100"
          : "bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-700"
      )}
      title={isEditing ? "Switch to Preview" : "Edit Content"}
    >
      {isEditing ? <Eye className="w-3 h-3" /> : <Edit3 className="w-3 h-3" />}
      {isEditing ? "Preview" : "Edit"}
    </button>
  );

  return (
    <AtomShell
      {...props}
      showCopy={!isEditing}
      variant="default"
      headerExtra={headerAction}
    >
      {() => {
        // [Mode 1] Editing Mode
        if (isEditing) {
          return (
            <div className="relative w-full min-h-[100px] animate-in fade-in duration-200">
              <TextareaAutosize
                value={localValue}
                onChange={handleChange}
                onBlur={handleBlur}
                minRows={5}
                placeholder="Enter markdown content..."
                className="w-full p-0 text-sm font-mono leading-relaxed bg-transparent outline-none resize-none text-slate-800 placeholder:text-slate-300"
                autoFocus
              />
              <div className="absolute bottom-0 right-0 p-2 pointer-events-none opacity-20">
                <FileText className="w-12 h-12 text-slate-400" />
              </div>
            </div>
          );
        }

        // [Mode 2] Viewing Mode
        const displayValue = localValue || "";

        if (isMarkdown) {
          return (
            <div
              className={cn(
                "rounded-lg transition-all",
                isTerminal && "bg-slate-900 text-slate-100 -m-4 p-4",
                !isReadOnly && !isTerminal && "hover:bg-slate-50/50 -m-2 p-2 rounded-xl cursor-text"
              )}
              onDoubleClick={() => !isReadOnly && !isTerminal && setIsEditing(true)}
              title={!isReadOnly && !isTerminal ? "Double click to edit" : undefined}
            >
              <MarkdownDisplay
                content={displayValue}
                className={cn(
                  isTerminal && "prose-invert font-mono text-sm prose-pre:bg-slate-800"
                )}
              />
            </div>
          );
        }

        return (
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed bg-slate-50/50 p-4 rounded-lg overflow-x-auto">
            {displayValue}
          </pre>
        );
      }}
    </AtomShell>
  );
};
