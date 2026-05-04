"use client";

import React, { useMemo } from "react";
import { cn } from "@/lib/utils";
import TextareaAutosize from "react-textarea-autosize";
import { CheckCircle, Plus, Trash2, RefreshCcw } from "lucide-react";
import { RenderAtomProps } from "@/app/types";
import { AtomShell, AtomRenderProps } from "../atoms/AtomShell";
import { useScaSelectionContext } from "@/app/components/renderer/utils/sca-selection-context";
// [FIX] Import the normalization utility
import { normalizeDataPayload } from "@/app/lib/abp-utils";

export const EntityScaPlanCard: React.FC<RenderAtomProps> = (props) => {
  const { actions, onAction, block, isSubmitting } = props;
  const scaContext = useScaSelectionContext();
  const showSelected = scaContext?.ignoreSelection ? false : block.meta?.is_selected;
  
  return (
    <AtomShell
      {...props}
      variant="default"
      headerExtra={showSelected && <CheckCircle className="w-4 h-4 text-emerald-600" />}
    >
      {(binding) => (
        <EntityScaPlanBody
          block={block}
          actions={actions}
          onAction={onAction}
          isSubmitting={isSubmitting}
          {...binding}
        />
      )}
    </AtomShell>
  );
};

function EntityScaPlanBody({
  block,
  actions,
  onAction,
  value,
  onChange,
  isReadOnly,
  isDirty,
  isSubmitting,
}: {
  block: RenderAtomProps["block"];
  actions: RenderAtomProps["actions"];
  onAction: RenderAtomProps["onAction"];
  isSubmitting?: boolean;
} & AtomRenderProps<any>) {
  
  const meta = block.meta || {};
  const scaContext = useScaSelectionContext();
  const isSelected = scaContext?.ignoreSelection ? false : meta.is_selected;

  // [DATA RESOLUTION FIX]
  // 1. Normalize the payload using the Defensive Adapter.
  // This handles raw objects, 'data' wrappers, and 'blocks' arrays (NodeOutput).
  const dataPayload = useMemo(() => {
      // Use binding value if available, otherwise block content
      const raw = value || block.content;
      return normalizeDataPayload(raw);
  }, [value, block.content]);
  
  // 2. Intelligent Key Recognition (Supports Node 1.3 sub-tasks & Node 3.1 paper structure)
  // Priority: outline (3.1) > sub_problem_list (1.3) > structure > items (Generic)
  const targetKey = 
    Array.isArray(dataPayload.outline) ? "outline" :
    Array.isArray(dataPayload.sub_problem_list) ? "sub_problem_list" :
    Array.isArray(dataPayload.structure) ? "structure" :
    Array.isArray(dataPayload.items) ? "items" : 
    null;

  // 3. Extract List Data
  // Handle complex object arrays (Structure) by adapting them to strings for the simple editor
  const rawList = targetKey ? dataPayload[targetKey] : [];
  
  // Adapter: Convert complex objects to simple editable strings
  const listItems: string[] = useMemo(() => {
      if (!Array.isArray(rawList)) return [];
      
      return rawList.map((item: any) => {
          if (typeof item === 'string') return item;
          if (typeof item === 'object' && item !== null) {
              // Prefer title for sections, or name, or fallback to JSON
              return item.title || item.name || JSON.stringify(item); 
          }
          return String(item);
      });
  }, [rawList]);

  // [UPDATE LOGIC]
  const updateList = (newSimpleList: string[]) => {
    if (isReadOnly || !targetKey) return;
    
    // Reconstruct Data:
    // If the original was an object array (Structure), try to preserve other fields
    const newListData = newSimpleList.map((str, idx) => {
        const original = rawList[idx];
        if (typeof original === 'object' && original !== null) {
            // Only update the title/display field, preserve ID/level/etc.
            return { ...original, title: str }; 
        }
        return str; // Pure string mode
    });

    // Construct the write-back object.
    // Note: We write back a CLEAN object based on dataPayload (which is already normalized).
    // This implicitly fixes the data structure in the DB if it was previously malformed/wrapped.
    const newData = { ...dataPayload, [targetKey]: newListData };
    
    onChange(newData);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Title & Description */}
      <div>
        <h3 className="font-bold text-base text-slate-900">{meta.title || block.label}</h3>
        {meta.description && <p className="text-xs text-slate-500 mt-1 leading-relaxed">{meta.description}</p>}
      </div>

      {/* List Editor Area */}
      <div
        className={cn(
          "rounded-xl border p-4 flex flex-col gap-3 transition-colors",
          isDirty ? "bg-amber-50/20 border-amber-200" : "bg-slate-50/50 border-slate-100"
        )}
      >
        <div className="flex justify-between items-center">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            {(targetKey === 'outline' || targetKey === 'sub_problem_list') ? 'Execution Plan' : 
             targetKey === 'structure' ? 'Paper Structure' :
             'Execution Plan'}
          </span>
          {!isReadOnly && targetKey && (
            <button
              onClick={() => updateList([...listItems, "New Item..."])}
              className="text-[10px] font-bold text-blue-600 hover:underline flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> Add Item
            </button>
          )}
        </div>

        <div className="space-y-2">
          {!targetKey && (
             <div className="flex flex-col gap-1 p-3 bg-red-50 border border-red-100 rounded-lg">
                <div className="text-xs font-bold text-red-500">Unrecognized Data Format</div>
                <div className="text-[10px] text-red-400 font-mono break-all">
                    Keys found: {Object.keys(dataPayload).join(", ")}
                </div>
             </div>
          )}
          {targetKey && listItems.length === 0 && <div className="text-xs text-slate-400 italic">Empty list.</div>}
          
          {listItems.map((item: string, idx: number) => (
            <div key={idx} className="flex gap-2 group/item items-start">
              <span className="text-[10px] font-mono text-slate-300 mt-2 w-4 shrink-0">
                {idx + 1}
              </span>
              <TextareaAutosize
                value={item}
                readOnly={isReadOnly}
                onChange={(e) => {
                  const next = [...listItems];
                  next[idx] = e.target.value;
                  updateList(next);
                }}
                className={cn(
                  "flex-1 text-xs p-2 rounded-lg border transition-all resize-none",
                  isReadOnly
                    ? "bg-transparent border-transparent px-0"
                    : "bg-white border-slate-200 focus:border-blue-300 focus:ring-1 focus:ring-blue-100 outline-none"
                )}
              />
              {!isReadOnly && (
                <button
                  onClick={() => updateList(listItems.filter((_, i) => i !== idx))}
                  className="opacity-0 group-hover/item:opacity-100 p-1.5 text-slate-300 hover:text-red-500 transition-all"
                  title="Remove Item"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* [FIX Issue 2] Footer Buttons Removed. 
          The 'Select' and 'Save' actions are now injected by backend and 
          rendered by <AtomShell> in the Header Toolbar. 
          
          We only keep the 'Reset' button if dirty, as a local helper.
      */}
      {!isReadOnly && isDirty && (
        <div className="flex justify-end border-t border-slate-100 pt-2">
            <button
              // [FIX] Reset logic should also respect the normalization if we want to support 'Reset to Original'
              // But strictly speaking, block.content might be the raw wrapped data.
              // Ideally, onChange should take normalized data.
              // For simplicity, we reset to block.content and let the useMemo above re-normalize it on next render.
              onClick={() => onChange(block.content)} 
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-500 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
              title="Discard changes"
            >
              <RefreshCcw className="w-3.5 h-3.5" /> Revert Changes
            </button>
        </div>
      )}
    </div>
  );
}
