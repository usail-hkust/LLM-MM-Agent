"use client";
import { ReactNode, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Copy, Check, Loader2 } from "lucide-react";
import { RenderAtomProps, BlockType } from "@/app/domain/abp"; // Import BlockType
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { useFormContext } from "react-hook-form";
import { ActionType } from "@/app/api/enums";
import * as Icons from "lucide-react";

export interface AtomRenderProps<T = any> {
  value: T;
  onChange: (val: T) => void;
  isReadOnly: boolean;
  isDirty: boolean;
  error?: string;
}

type AtomShellProps = Omit<RenderAtomProps, "children"> & {
  label?: string;
  icon?: React.ComponentType<{ className?: string }>;
  contentToCopy?: string;
  children: ReactNode | ((binding: AtomRenderProps) => ReactNode);
  variant?: "default" | "ghost" | "fill";
  hideHeader?: boolean;
  showCopy?: boolean;
  headerExtra?: ReactNode;
};

export function AtomShell({
  label,
  icon: Icon,
  contentToCopy,
  children,
  variant = "default",
  hideHeader = false,
  showCopy = false,
  headerExtra,
  actions = [], 
  onAction,
  isSubmitting,
  block, // block is destructured here, removing it from bindingProps
  ...bindingProps
}: AtomShellProps) {
  const [copied, setCopied] = useState(false);
  
  // [CRITICAL FIX] Reconstruct the full props object including 'block'
  // Prop stripping via destructuring caused 'block' to be undefined in the hook
  const binding = useAtomBinding({ 
    ...bindingProps, 
    block, 
    actions, 
    onAction, 
    isSubmitting 
  });
  const formContext = useFormContext();
  const isDirty = formContext?.formState?.isDirty ?? false;

  // [FIX] Visual Collapse Check
  // Even if layout passed it, if dynamic value becomes empty (e.g. streaming start),
  // we want to avoid showing an empty bordered box.
  const isEmptyContent = useMemo(() => {
      // Allow editor/code to be empty
      if (block?.type === BlockType.CODE) return false;
      // Allow editing mode text to be initially empty
      if (binding.value === "" && !binding.isReadOnly) return false;
      
      const val = binding.value;
      if (val === null || val === undefined) return true;
      if (typeof val === 'string' && !val.trim()) return true;
      // Empty object/array check
      if (typeof val === 'object') {
          if (Array.isArray(val)) return val.length === 0;
          return Object.keys(val).length === 0;
      }
      return false;
  }, [binding.value, block?.type, binding.isReadOnly]);

  // Logic: If it's a "Ghost" variant (no border) or explicitly allowed empty, don't collapse.
  // But if it's "Default" (Bordered Card) and empty, it looks like a bug.
  // Exception: If actions are present (e.g. just a button bar), show it.
  const shouldVisualCollapse = variant === "default" && isEmptyContent && actions.length === 0 && !label;

  if (shouldVisualCollapse) {
      return null;
  }

  // ... (Existing handleCopy, toolbarButtons logic) ...
  // [Re-paste existing logic for handleCopy and toolbarButtons]
  const handleCopy = () => {
    const val = contentToCopy ?? (typeof binding.value === 'string' ? binding.value : JSON.stringify(binding.value));
    navigator.clipboard.writeText(val);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toolbarButtons = useMemo(() => {
    return actions.map(action => {
       const isDisabled = isSubmitting || (action.validation_rule === "require_dirty" && !isDirty);
       const isLoading = isSubmitting && action.type === ActionType.PRIMARY;
       const BtnIcon = action.icon ? (Icons as any)[action.icon] : undefined;
       
       return (
          <button
            key={action.id}
            onClick={() => {
                const currentData = formContext ? formContext.getValues() : {};
                
                // [FIX] Vector Payload Construction
                // Ensure 'new_content' (the vector state) is explicitly included in the payload
                // so the backend can perform batch updates.
                const vectorPayload: any = {
                    ...action.payload,
                    // If the form has new_content, pass it. Otherwise empty dict.
                    new_content: currentData.new_content || {}
                };
                
                // Backward Compatibility / Scalar Logic
                const isSaveAction = 
                    action.id.includes("save") || 
                    (vectorPayload as any).action === "save_draft" ||
                    action.validation_rule === "require_dirty";

                const isRunAction = 
                    action.id.includes("run") || 
                    (vectorPayload as any).action === "run_node" ||
                    (vectorPayload as any).intent === "execute_only";

                if (block) {
                    if (isSaveAction) {
                        const bindingKey = block.data_key || block.id;
                        const specificValue = currentData.new_content?.[bindingKey];
                        // Ensure the specific content being saved matches the form state
                        if (specificValue !== undefined) {
                            vectorPayload.content = specificValue;
                        } else {
                            vectorPayload.content = binding.value;
                        }
                    }
                    else if (isRunAction) {
                        // Inject current block value as 'manual_content' for legacy scalar logic fallback
                        vectorPayload.manual_content = binding.value;
                        if (!vectorPayload.block_id) {
                            vectorPayload.block_id = block.id;
                        }
                        
                        // [CRITICAL] Force include form data if not already present
                        // RHF getValues() returns nested structure { new_content: {...} }
                        // merging { ...currentData } ensures new_content is at root of payload
                        Object.assign(vectorPayload, currentData);
                    }
                }

                // Dispatch
                onAction({ ...action, payload: vectorPayload });
            }}
            disabled={isDisabled}
            className={cn(
               "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold transition-all uppercase ml-2",
               action.type === ActionType.PRIMARY 
                 ? "bg-blue-600 text-white hover:bg-blue-700 shadow-sm" 
                 : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50",
               isDisabled && "opacity-50 cursor-not-allowed"
            )}
            title={action.label}
          >
            {isLoading ? <Loader2 className="w-3 h-3 animate-spin"/> : BtnIcon && <BtnIcon className="w-3 h-3"/>}
            {action.label}
          </button>
       );
    });
  }, [actions, isSubmitting, isDirty, onAction, formContext, block, binding.value]);

  const resolvedCopyContent =
    contentToCopy ??
    (showCopy ? serializeCopyValue(binding.value) : undefined);

  const renderedChildren = typeof children === "function" ? children(binding) : children;

  return (
    <div
      className={cn(
        "w-full transition-all duration-300 flex flex-col overflow-hidden",
        variant === "default" && "border border-slate-200 bg-white rounded-xl shadow-sm",
        variant === "ghost" && "bg-transparent border-none shadow-none",
        variant === "fill" && "h-full min-h-0 rounded-none border-none shadow-none bg-white"
      )}
    >
      {!hideHeader && (
        <div className={cn("px-4 py-2 border-b flex justify-between items-center shrink-0 select-none min-h-[40px]", variant === "fill" ? "bg-slate-50 border-slate-200" : "bg-white/50 border-slate-100")}>
          <div className="flex items-center gap-2 overflow-hidden">
            {Icon && <Icon className="w-4 h-4 text-slate-400" />}
            {label && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider truncate">{label}</span>}
            {binding.isDirty && !binding.isReadOnly && <span className="w-1.5 h-1.5 rounded-full bg-amber-400" title="Unsaved changes" />}
          </div>
          <div className="flex items-center gap-1 shrink-0 ml-4">
            {toolbarButtons}
            {/* [FIX] Ensure headerExtra (Edit Button) is separated from actions */}
            {(headerExtra || (actions.length > 0 && showCopy)) && <div className="w-px h-3 bg-slate-200 mx-1" />}
            {headerExtra && <div className="shrink-0">{headerExtra}</div>}
            {showCopy && (
              <button onClick={handleCopy} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-slate-100 rounded-md transition-all">
                {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>
      )}
      {/* [FIX] Ensure empty children doesn't force height via padding */}
      <div className={cn("flex-1 min-h-0", variant === "default" ? "p-4" : "p-0")}>
        {renderedChildren}
      </div>
    </div>
  );
}

function serializeCopyValue(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
