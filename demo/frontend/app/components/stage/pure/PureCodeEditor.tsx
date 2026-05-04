"use client";

import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import Editor, { loader, useMonaco } from "@monaco-editor/react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PureCodeEditorRef {
  insertText: (text: string) => void;
  getValue: () => string;
}

interface PureCodeEditorProps {
  value: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (val: string) => void;
  errorLines?: number[];
  className?: string;
  // [NEW] Allow injecting bottom padding for overlapping layouts
  paddingBottom?: number;
  // [CRITICAL FIX] Expose onMount to allow parent components to attach low-level listeners
  onMount?: (editor: any, monaco: any) => void;
}

export const PureCodeEditor = forwardRef<PureCodeEditorRef, PureCodeEditorProps>(
  (
    {
      value,
      language = "python",
      readOnly = false,
      onChange,
      errorLines = [],
      className,
      paddingBottom = 12, // Default
      onMount, // [FIX] Destructure new prop
    },
    ref
  ) => {
    const editorRef = useRef<any>(null);
    const monaco = useMonaco();
    const decorationsRef = useRef<string[]>([]);
    const commandQueueRef = useRef<Array<(editor: any) => void>>([]);

    useEffect(() => {
      loader.config({
        paths: {
          vs:
            process.env.NEXT_PUBLIC_MONACO_BASE_URL ||
            "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs",
        },
      });
    }, []);

    useImperativeHandle(ref, () => ({
      insertText: (text: string) => {
        const operation = (editor: any) => {
          const selection = editor.getSelection();
          const op = { range: selection, text, forceMoveMarkers: true };
          editor.executeEdits("atom-insert", [op]);
          editor.revealPositionInCenterIfOutsideViewport(editor.getPosition());
          editor.focus();
        };

        if (editorRef.current) {
          operation(editorRef.current);
        } else {
          commandQueueRef.current.push(operation);
        }
      },
      getValue: () => editorRef.current?.getValue() || value || "",
    }));

    useEffect(() => {
      if (!monaco || !editorRef.current) return;
      const model = editorRef.current.getModel();
      if (!model) return;

      if (!errorLines.length) {
        decorationsRef.current = editorRef.current.deltaDecorations(
          decorationsRef.current,
          []
        );
        return;
      }

      const newDecorations = errorLines.map((line) => ({
        range: new monaco.Range(line, 1, line, 1),
        options: {
          isWholeLine: true,
          className: "monaco-error-line",
          glyphMarginClassName: "monaco-error-glyph",
          hoverMessage: { value: "**Error**: Check logs." },
          minimap: { color: "#ef4444", position: 1 },
          overviewRuler: { color: "#ef4444", position: 1 },
        },
      }));
      decorationsRef.current = editorRef.current.deltaDecorations(
        decorationsRef.current,
        newDecorations
      );
      editorRef.current.revealLineInCenter(errorLines[0]);
    }, [errorLines, monaco]);

    const handleEditorDidMount = (editor: any, monacoInstance: any) => {
      editorRef.current = editor;

      // [FIX] Forward to parent prop if provided
      if (onMount) {
        onMount(editor, monacoInstance);
      }

      if (commandQueueRef.current.length > 0) {
        commandQueueRef.current.forEach((cmd) => cmd(editor));
        commandQueueRef.current = [];
      }
    };

    const monacoLang = language === "latex" ? "latex" : language;

    return (
      <div className={cn("relative w-full h-full min-h-[200px]", className)}>
        <Editor
          height="100%"
          language={monacoLang}
          value={value}
          onChange={(val) => !readOnly && onChange?.(val || "")}
          onMount={handleEditorDidMount}
          loading={
            <div className="flex items-center justify-center h-full text-slate-400 gap-2 text-xs">
              <Loader2 className="w-4 h-4 animate-spin" />
              Initializing...
            </div>
          }
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "var(--font-geist-mono)",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: language === "latex" ? "on" : "off",
            // [FIX] Inject dynamic padding to allow scrolling past Floating Dock
            padding: { top: 12, bottom: paddingBottom },
            renderLineHighlight: readOnly ? "none" : "all",
            glyphMargin: true,
          }}
        />
      </div>
    );
  }
);

PureCodeEditor.displayName = "PureCodeEditor";
