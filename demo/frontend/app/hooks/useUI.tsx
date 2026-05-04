"use client";

import React, {
  createContext,
  ReactNode,
  useContext,
  useMemo,
  useState,
  useRef,
  useEffect
} from "react";
import { cn } from "@/lib/utils";
import {
  AlertCircle,
  Info,
  HelpCircle,
  MessageSquare,
  AlertTriangle,
  Trash2,
  ChevronDown
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DialogOptions {
  title?: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  multiline?: boolean;
  defaultValue?: string;
  danger?: boolean;
  placeholder?: string;
  icon?: React.ElementType; 
  // [NEW] Allow explicit control over whether input is required (default: true for prompt)
  required?: boolean;
  // [NEW]
  inputType?: "text" | "textarea" | "select";
  options?: { label: string; value: string }[] | string[];
}

interface UIContextType {
  toast: {
    success: (msg: string) => void;
    error: (msg: string) => void;
    info: (msg: string) => void;
  };
  dialog: {
    alert: (msg: string, options?: DialogOptions) => Promise<void>;
    confirm: (msg: string, options?: DialogOptions) => Promise<boolean>;
    prompt: (msg: string, options?: DialogOptions) => Promise<string | null>;
  };
}

const UIContext = createContext<UIContextType | null>(null);

export function useUI() {
  const context = useContext(UIContext);
  if (!context) throw new Error("useUI must be used within a UIProvider");
  return context;
}

// --- Internal Components for Dialog Content ---

function DialogIcon({ type, danger, customIcon: CustomIcon }: { type: string; danger?: boolean; customIcon?: React.ElementType }) {
  if (CustomIcon) return <CustomIcon className={cn("w-5 h-5", danger ? "text-red-500" : "text-slate-500")} />;
  
  if (type === "confirm") {
    return danger ? <AlertTriangle className="w-5 h-5 text-red-500" /> : <HelpCircle className="w-5 h-5 text-blue-500" />;
  }
  if (type === "prompt") {
    return danger ? <MessageSquare className="w-5 h-5 text-red-500" /> : <MessageSquare className="w-5 h-5 text-blue-500" />;
  }
  return <Info className="w-5 h-5 text-slate-500" />;
}

// Wrapper to bridge the controlled state from Provider to Content
function PromptContentWrapper({ defaultValue, message, options, onChange, onConfirm }: any) {
    const initVal = defaultValue || (options.inputType === "select" && options.options?.[0] ? (typeof options.options[0] === 'string' ? options.options[0] : options.options[0].value) : "");
    const [localValue, setLocalValue] = useState(initVal);
    
    useEffect(() => onChange(localValue), [localValue, onChange]);
    const selectOptions = useMemo(() => options.options?.map((o:any) => typeof o === 'string' ? {label:o, value:o} : o) || [], [options.options]);

    return (
        <div className="space-y-4">
          <p className="text-sm text-slate-600 whitespace-pre-wrap">{message}</p>
          <div className="relative">
            {options.inputType === "select" ? (
                <div className="relative">
                    <select className="w-full border rounded-xl p-3 appearance-none bg-slate-50 outline-none" value={localValue} onChange={(e) => setLocalValue(e.target.value)}>
                        {selectOptions.map((opt: any) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                    </select>
                    <ChevronDown className="absolute right-3 top-3 w-4 h-4 text-slate-400 pointer-events-none"/>
                </div>
            ) : options.inputType === "textarea" ? (
                <textarea className="w-full border rounded-xl p-3 min-h-[100px] bg-slate-50 resize-none outline-none" value={localValue} onChange={(e) => setLocalValue(e.target.value)} placeholder={options.placeholder}/>
            ) : (
                <input className="w-full border rounded-xl p-3 bg-slate-50 outline-none" type="text" value={localValue} onChange={(e) => setLocalValue(e.target.value)} placeholder={options.placeholder} onKeyDown={(e) => e.key==='Enter' && onConfirm(localValue)}/>
            )}
          </div>
        </div>
    );
}

// --- Provider ---

export function UIProvider({ children }: { children: ReactNode }) {
  // Dialog State
  const [dialogState, setDialogState] = useState<{
    isOpen: boolean;
    type: "alert" | "confirm" | "prompt";
    message: string;
    options: DialogOptions;
    resolve: (value: any) => void;
  } | null>(null);
  
  // Need to lift state up for footer button disabling logic
  const [promptValue, setPromptValue] = useState("");

  // --- Dialog API ---
  const ui = useMemo<UIContextType>(
    () => ({
      toast: {
        success: toast.success,
        error: toast.error,
        info: toast.info,
      },
      dialog: {
        alert: (msg, options = {}) =>
          new Promise((resolve) => {
            setDialogState({ isOpen: true, type: "alert", message: msg, options, resolve });
          }),
        confirm: (msg, options = {}) =>
          new Promise((resolve) => {
            setDialogState({ isOpen: true, type: "confirm", message: msg, options, resolve });
          }),
        prompt: (msg, options = {}) =>
          new Promise((resolve) => {
            setPromptValue(options.defaultValue || "");
            setDialogState({ isOpen: true, type: "prompt", message: msg, options, resolve });
          }),
      },
    }),
    [],
  );

  const handleClose = (result: any) => {
    if (dialogState?.resolve) dialogState.resolve(result);
    setDialogState((prev) => (prev ? { ...prev, isOpen: false } : null));
    setTimeout(() => setDialogState(null), 300);
    setPromptValue("");
  };

  // Helper to determine if prompt submit should be disabled
  const isPromptSubmitDisabled = 
    dialogState?.type === "prompt" && 
    dialogState?.options.required !== false && // Default to required=true
    !promptValue.trim();

  return (
    <UIContext.Provider value={ui}>
      {children}

      {/* --- Global Dialog Modal --- */}
      {dialogState && (
        <Dialog
          open={dialogState.isOpen}
          onOpenChange={(open) => {
            if (!open) handleClose(dialogState.type === "confirm" ? false : null);
          }}
        >
          <DialogContent className="max-w-md overflow-hidden p-0">
            <div
              className={cn(
                "px-6 py-5 border-b",
                dialogState.options.danger ? "bg-red-50/80 border-red-100" : "bg-white border-slate-100"
              )}
            >
              <DialogHeader>
                <DialogTitle
                  className={cn(
                    "text-lg font-bold leading-tight flex items-center gap-2.5",
                    dialogState.options.danger ? "text-red-700" : "text-slate-800"
                  )}
                >
                  <span
                    className={cn(
                      "p-1.5 rounded-lg",
                      dialogState.options.danger ? "bg-red-100" : "bg-slate-100"
                    )}
                  >
                    <DialogIcon
                      type={dialogState.type}
                      danger={dialogState.options.danger}
                      customIcon={dialogState.options.icon}
                    />
                  </span>
                  <span>
                    {dialogState.options.title ||
                      (dialogState.type === "confirm" ? "Confirm Action" : "Notice")}
                  </span>
                </DialogTitle>
                {dialogState.options.description && (
                  <DialogDescription
                    className={cn(
                      "text-xs mt-1.5 leading-relaxed",
                      dialogState.options.danger ? "text-red-600/80" : "text-slate-500"
                    )}
                  >
                    {dialogState.options.description}
                  </DialogDescription>
                )}
              </DialogHeader>
            </div>

            <div className="p-6">
              <div className="space-y-4">
                {/* Content Switching */}
                {dialogState.type === "prompt" ? (
                  // We pass setPromptValue down so we can update state for validation
                  // We render a wrapper that handles the input logic
                  <PromptContentWrapper
                    defaultValue={dialogState.options.defaultValue || ""}
                    message={dialogState.message}
                    options={dialogState.options}
                    onChange={setPromptValue}
                    onConfirm={(val: string) => handleClose(val)}
                  />
                ) : (
                  <p className="text-sm text-slate-600 leading-relaxed font-medium">
                    {dialogState.message}
                  </p>
                )}
              </div>
            </div>

            <DialogFooter className="px-6 py-4 bg-slate-50/80 border-t border-slate-100">
              {dialogState.type !== "alert" && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => handleClose(dialogState.type === "confirm" ? false : null)}
                  className="text-slate-500 hover:text-slate-700"
                >
                  {dialogState.options.cancelText || "Cancel"}
                </Button>
              )}

              <Button
                type="button"
                variant={dialogState.options.danger ? "destructive" : "default"}
                onClick={() => handleClose(dialogState.type === "prompt" ? promptValue : true)}
                disabled={isPromptSubmitDisabled}
                className={cn("gap-2", isPromptSubmitDisabled && "opacity-50")}
              >
                {dialogState.options.danger && dialogState.type !== "prompt" && <Trash2 className="w-4 h-4" />}
                {dialogState.options.confirmText || "Confirm"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </UIContext.Provider>
  );
}
