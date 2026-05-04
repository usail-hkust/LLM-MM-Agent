"use client";
import React, { useRef, useState, useEffect } from "react";
import { useBlockDraft } from "@/app/hooks/useBlockDraft";
import { PureCodeEditor } from "@/app/components/stage/pure/PureCodeEditor";
import { Terminal } from "lucide-react";
import { RenderAtomProps } from "@/app/domain/abp";
import { AtomShell } from "./AtomShell";
import { useLayoutContext } from "@/app/context/LayoutContext";

export function AtomCode(props: RenderAtomProps) {
  const { block, state } = props;
  const isReadOnly = state.read_only;
  
  // 1. Data Layer: Hook manages Sync Logic & Dirty State
  const { value, onChange } = useBlockDraft(block, isReadOnly);
  
  const lang = block.meta?.language || "python";
  const errorLines = block.meta?.error_lines || [];
  const { isFixed, contentBottomPadding } = useLayoutContext();

  // 2. View Layer: Local State Buffer
  // Acts as the Single Source of Truth for the UI to prevent external interference
  const [localCode, setLocalCode] = useState(String(value || ""));
  
  // 3. View Layer: Focus Guard
  const isFocusedRef = useRef(false);

  // [CRITICAL FIX] Focus-Aware Sync Strategy
  // Only sync external updates (from useBlockDraft) to local state if:
  // - The editor is NOT focused (User is not typing)
  // - AND the value has actually changed
  useEffect(() => {
    if (!isFocusedRef.current) {
        const externalVal = String(value || "");
        if (externalVal !== localCode) {
            setLocalCode(externalVal);
        }
    }
    // Note: We deliberately exclude localCode from deps to avoid loops. 
    // We only react to upstream `value` changes.
  }, [value]);

  // Handle User Input
  const handleEditorChange = (newVal: string) => {
      // 1. Update UI immediately
      setLocalCode(newVal);
      // 2. Propagate to Hook (Debounced Save)
      onChange(newVal);
  };

  // Attach Focus Listeners via Monaco Instance
  const handleMount = (editor: any) => {
      editor.onDidFocusEditorText(() => {
          isFocusedRef.current = true;
      });
      editor.onDidBlurEditorText(() => {
          isFocusedRef.current = false;
          // Optional: On blur, we could force a re-sync check if needed, 
          // but the useEffect above handles it on next render cycle if value differs.
      });
  };

  return (
      <AtomShell 
          {...props}
          label={lang} 
          icon={Terminal} 
          showCopy 
          variant="fill"
      >
          {() => (
            <PureCodeEditor 
              value={localCode} // Bind to Local Buffer
              onChange={handleEditorChange} 
              onMount={handleMount} // Attach Listeners
              readOnly={isReadOnly} 
              language={lang} 
              errorLines={Array.isArray(errorLines) ? errorLines : []}
              paddingBottom={contentBottomPadding}
              className={isFixed ? "h-full" : "h-full min-h-[500px]"}
            />
          )}
      </AtomShell>
  );
}
