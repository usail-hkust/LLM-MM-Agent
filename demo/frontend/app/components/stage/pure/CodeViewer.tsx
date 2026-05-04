"use client";

import { useState, useRef, useImperativeHandle, forwardRef } from "react";
import { Code, Terminal, FileText, Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { PureCodeEditor, PureCodeEditorRef } from "@/app/components/stage/pure/PureCodeEditor";

// [New] Define the imperative handle interface
export interface CodeViewerRef {
  insertText: (text: string) => void;
  getValue: () => string; // [Added] For Workbench compatibility
}

interface CodeViewerProps {
  code: string; // Acts as initialValue in Workbench mode if uncontrolled, or value if controlled
  executionResult?: unknown;
  language?: string;
  readOnly?: boolean;
  onChange?: (val: string) => void;
  className?: string;
  label?: string; // [Added] To support custom header labels
  mode?: "simple" | "workbench"; // "simple" = Pure Viewer, "workbench" = Full Editor
  errorLines?: number[];
}

export const CodeViewer = forwardRef<CodeViewerRef, CodeViewerProps>(
  (
    {
      code,
      executionResult,
      language = "python",
      readOnly = false,
      onChange,
      className,
      label,
      mode = "simple",
      errorLines = [],
    },
    ref
  ) => {
    const [copied, setCopied] = useState(false);
    const editorRef = useRef<PureCodeEditorRef>(null);

    useImperativeHandle(ref, () => ({
      insertText: (text: string) => editorRef.current?.insertText(text),
      getValue: () => editorRef.current?.getValue() || code || "",
    }));

    const handleCopy = () => {
      const val = editorRef.current?.getValue() || code;
      navigator.clipboard.writeText(val);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    const displayLabel = label || (language === "latex" ? "LaTeX Source" : "Python Source");
    const LangIcon = language === "latex" ? FileText : Code;

    return (
      <div className={cn("flex flex-col h-full min-h-0", className)}>
        <div
          className={cn(
            "flex-1 flex flex-col overflow-hidden transition-colors duration-300",
            // In workbench mode, we might want no border if the parent handles it,
            // or consistent styling. Let's stick to consistent styling.
            mode === "workbench"
              ? "bg-white" // Workbench usually has its own container border
              : readOnly
              ? "border border-slate-200 bg-slate-50/30 rounded-xl"
              : "border border-slate-300 bg-white rounded-xl shadow-sm"
          )}
        >
          {/* Header: Render for both modes to ensure consistency, but style slightly differently if needed */}
          <div
            className={cn(
              "px-4 py-2 border-b flex justify-between items-center shrink-0",
              mode === "workbench" ? "bg-slate-50 border-slate-200" : "bg-white border-slate-100"
            )}
          >
            <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider">
              {mode === "simple" && <LangIcon className="w-4 h-4 text-blue-500" />}
              {displayLabel}
            </div>
            <div className="flex items-center gap-2">
              {readOnly && (
                <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded font-mono border border-slate-200">
                  READ ONLY
                </span>
              )}
              {!readOnly && mode === "simple" && (
                <button
                  onClick={handleCopy}
                  className="text-slate-400 hover:text-slate-600 transition-colors"
                  title="Copy Code"
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 relative min-h-0">
            <PureCodeEditor
              ref={editorRef}
              value={code}
              language={language}
              readOnly={readOnly}
              onChange={onChange}
              errorLines={errorLines}
              className="h-full"
            />
          </div>
        </div>

        {/* Execution Result Panel (Only for Simple Mode / AutoPlayer) */}
        {mode === "simple" && executionResult !== undefined && executionResult !== null && (
          <div className="shrink-0 max-h-48 flex flex-col rounded-xl border border-slate-200 overflow-hidden bg-white shadow-sm mt-4 animate-enter">
            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex items-center gap-2 text-xs font-bold text-slate-500 uppercase">
              <Terminal className="w-4 h-4 text-slate-700" />
              Execution Output
            </div>
            <pre className="p-4 text-xs font-mono text-slate-700 whitespace-pre-wrap overflow-auto bg-white custom-scrollbar">
              {typeof executionResult === "string"
                ? executionResult
                : JSON.stringify(executionResult, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }
);
CodeViewer.displayName = "CodeViewer";
