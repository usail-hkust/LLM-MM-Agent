"use client";

import { cn } from "@/lib/utils";
import {
  CheckCircle,
  MessageSquare,
  Edit3,
  ListChecks,
  FileText,
  FileType,
  ChevronRight,
  Layers,
} from "lucide-react";
import { useMemo } from "react";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";

interface ScaOptionCardProps {
  id: string;
  title: string;
  description?: string;
  aiAnalysis?: string;
  data?: Record<string, any>;
  isManuallyEdited?: boolean;
  isSelected?: boolean;
  isRejected?: boolean;
  readOnly?: boolean;
  feedback?: string;
  onSelect?: () => void;
  onEdit?: () => void;
}

export function ScaOptionCard({
  title,
  description,
  aiAnalysis,
  data,
  isManuallyEdited,
  isSelected,
  isRejected,
  readOnly,
  feedback,
  onSelect,
  onEdit,
}: ScaOptionCardProps) {
  const preview = useMemo(() => {
    if (!data) return null;

    // [FIX 1] 扩展列表数据的识别逻辑，加入 'outline'
    // 优先级：Outline (3.1) > Execution Plan (1.3) > Generic Problems
    const listData = data.outline || data.sub_problem_list || data.problems;

    if (Array.isArray(listData) && listData.length > 0) {
      return {
        mode: "list",
        // [FIX 2] 统一 Label 为 "Execution Plan"，统一图标为 ListChecks (与 1.3 一致)
        label: "Execution Plan",
        icon: ListChecks,
        items: listData.slice(0, 4),
        count: listData.length,
      };
    }

    if (data.model_blueprint) {
      if (typeof data.model_blueprint === "object") {
        const bp = data.model_blueprint;
        return {
          mode: "dict",
          label: "Model Blueprint",
          icon: Layers,
          items: [
            { key: "Model Name", val: bp.name || bp.model_name },
            { key: "Rationale", val: bp.rationale || bp.description },
            { key: "Complexity", val: bp.complexity || "Standard" },
          ].filter((i) => i.val),
        };
      }

      if (typeof data.model_blueprint === "string") {
        return {
          mode: "dict",
          label: "Model Blueprint",
          icon: Layers,
          items: [
            { key: "Preview", val: data.model_blueprint },
          ],
        };
      }
    }

    if (data.paper_schema && typeof data.paper_schema === "object") {
      const schema = data.paper_schema;
      const sections = Array.isArray(schema.sections) ? schema.sections : [];
      return {
        mode: "tree",
        label: "Paper Structure",
        icon: FileType,
        title: schema.metadata?.title || "Untitled Paper",
        sections: sections.slice(0, 4).map((s: any) => s.title),
        total: sections.length,
      };
    }

    const keys = Object.keys(data).filter((k) => k !== "id");
    if (keys.length > 0) {
      return {
        mode: "generic",
        label: "Data Payload",
        icon: FileText,
        keys: keys.slice(0, 3),
        count: keys.length,
      };
    }

    return null;
  }, [data]);

  return (
    <div
      className={cn(
        "relative flex flex-col p-5 rounded-xl border transition-all duration-300 group overflow-hidden bg-white",
        isSelected
          ? "border-black ring-1 ring-black shadow-md z-10"
          : isRejected
            ? "border-red-200 bg-red-50/30 opacity-60 grayscale-[0.5]"
            : "border-slate-200 hover:border-slate-300 hover:shadow-sm",
        readOnly && !isSelected && "opacity-90"
      )}
    >
      {isSelected && <div className="absolute top-0 left-0 w-full h-1 bg-black" />}

      <div className="flex justify-between items-start mb-3">
        <h3
          className={cn(
            "font-bold text-lg leading-tight pr-4 transition-colors",
            isSelected ? "text-black" : "text-slate-800"
          )}
        >
          {title}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          {isManuallyEdited && !isSelected && (
            <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200 font-bold uppercase tracking-wide">
              Edited
            </span>
          )}
          {isSelected && <CheckCircle className="w-6 h-6 text-black fill-white" />}
        </div>
      </div>

      {/* 
         [OPTIMIZATION] Scrollable description area instead of truncation 
         Removed: line-clamp-3
         Added: max-h-[300px], overflow-y-auto, custom-scrollbar
      */}
      <div className="text-sm text-slate-600 mb-5 leading-relaxed min-h-[1.5rem] max-h-[300px] overflow-y-auto custom-scrollbar pr-1">
        {description ? (
          <MarkdownDisplay content={description} className="prose-p:m-0 prose-p:leading-relaxed text-sm text-slate-600" />
        ) : (
          <span className="italic text-slate-400">No description provided.</span>
        )}
      </div>

      {preview && (
        <div className="mb-5 bg-slate-50/80 rounded-lg border border-slate-100 p-3.5">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">
            <preview.icon className="w-3.5 h-3.5" />
            {preview.label}
          </div>

          {preview.mode === "list" && (
            <ul className="space-y-1.5">
              {(preview.items as string[]).map((item, i) => (
                <li key={i} className="text-xs text-slate-700 flex gap-2 items-start leading-snug">
                  <span className="text-slate-300 font-mono text-[10px] pt-0.5 select-none">
                    {(i + 1).toString().padStart(2, "0")}
                  </span>
                  <span className="line-clamp-2">{item}</span>
                </li>
              ))}
            </ul>
          )}

          {preview.mode === "dict" && (
            <div className="space-y-2.5">
              {(preview.items as any[]).map((item, i) => (
                <div key={i}>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">{item.key}</div>
                  <div className="text-xs text-slate-700 leading-relaxed mt-0.5 border-l-2 border-slate-200 pl-2">
                    {/* [FIX] Render blueprint values as markdown */}
                    <MarkdownDisplay content={String(item.val)} className="prose-p:m-0" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {preview.mode === "tree" && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 bg-white border border-slate-100 p-1.5 rounded-md shadow-sm">
                <FileText className="w-3.5 h-3.5 text-blue-500" />
                <span className="truncate">{preview.title}</span>
              </div>
              <div className="pl-2 border-l border-slate-200 ml-2 space-y-1 py-1">
                {(preview.sections as string[]).map((sec, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[11px] text-slate-600">
                    <ChevronRight className="w-3 h-3 text-slate-300" />
                    <span className="truncate">{sec}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {preview.mode === "generic" && (
            <div className="space-y-1.5">
              <div className="text-[11px] text-slate-600">
                Keys: {(preview.keys as string[]).join(", ")}
              </div>
               {preview.count && preview.count > (preview.keys as string[]).length && (
                <div className="text-[10px] text-slate-400">
                  + {preview.count - (preview.keys as string[]).length} more
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {aiAnalysis && !preview && (
        <div className="bg-blue-50/50 text-slate-700 text-xs p-3 rounded-lg border border-blue-100/50 mb-4">
          <span className="font-bold text-blue-400 uppercase tracking-wider text-[10px] block mb-2">
            AI Analysis
          </span>
          <MarkdownDisplay content={aiAnalysis} className="text-xs leading-relaxed prose-p:my-1" />
        </div>
      )}

      {feedback && (
        <div className="mt-auto mb-4 bg-red-50 text-red-800 text-xs p-3 rounded-lg border border-red-100 flex gap-2 items-start">
          <MessageSquare className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <span className="font-bold block text-[10px] uppercase opacity-70 mb-1">Rejection Reason</span>
            <MarkdownDisplay content={feedback} className="text-xs text-red-800 prose-red prose-p:m-0" />
          </div>
        </div>
      )}

      {!readOnly && (
        <div className="mt-auto flex gap-2 pt-2 border-t border-slate-50">
          <button
            onClick={onSelect}
            className={cn(
              "flex-1 py-2.5 rounded-xl text-sm font-bold transition-all shadow-sm flex items-center justify-center gap-2",
              isSelected
                ? "bg-black text-white cursor-default"
                : "bg-white border border-slate-200 text-slate-700 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50"
            )}
            disabled={isSelected}
          >
            {isSelected ? "Selected" : "Select Strategy"}
          </button>

          <button
            onClick={onEdit}
            className="p-2.5 border border-slate-200 bg-white rounded-xl text-slate-500 hover:text-blue-600 hover:border-blue-300 hover:bg-blue-50 transition-colors ml-auto"
            title="Edit Option"
          >
            <Edit3 className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
