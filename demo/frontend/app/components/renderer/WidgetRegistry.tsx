"use client";
import React from "react";
import { RenderType, BlockType, RenderAtomProps } from "@/app/domain/abp";
import { ExecutionLog } from "@/app/types";
import { AtomText } from "./widgets/atoms/AtomText";
import { AtomCode } from "./widgets/atoms/AtomCode";
import { AtomData } from "./widgets/atoms/AtomData";
import { AtomArtifacts } from "./widgets/atoms/AtomArtifacts";
import { AtomLogs } from "./widgets/atoms/AtomLogs";
import { AtomInput } from "./widgets/atoms/AtomInput";
import { SmartConsole } from "@/app/components/stage/atoms/SmartConsole";
import { EntityScaCard } from "./widgets/entities/EntityScaCard";
import { EntityScaPlanCard } from "./widgets/entities/EntityScaPlanCard";
import { EntityAvlItem } from "./widgets/entities/EntityAvlItem";
import { EntityVarlCard } from "./widgets/entities/EntityVarlCard";
import { EntityResultCard } from "./widgets/entities/EntityResultCard";
import { EntityIdeWorkspace } from "./widgets/entities/EntityIdeWorkspace";
// Layouts
import { StackLayout } from "./widgets/layout/StackLayout";
import { GridLayout } from "./widgets/layout/GridLayout";
import { TabsLayout } from "./widgets/layout/TabsLayout";
import { SplitLayout } from "./widgets/layout/SplitLayout";

// [FIX] Adapter: Raw Text Block -> SmartConsole Structure
import { buildExecutionLogs } from "./utils/logParsing";

// [FIX] Adapter: ContentBlock -> SmartConsole Props
const AtomSmartConsoleAdapter: React.FC<RenderAtomProps> = ({ block }) => {
  const logs = React.useMemo(() => {
    const raw = block.content;
    // Case 1: Already structured (rare in V2)
    if (Array.isArray(raw)) return raw;

    // Case 2: Parse raw string
    // Use tags to determine if it's stderr or stdout by default
    const defaultType = block.tags?.includes("stderr") || block.tags?.includes("error")
      ? "stderr"
      : "stdout";

    // [FIX] Safe conversion for objects
    const contentStr = (typeof raw === "object" && raw !== null)
      ? JSON.stringify(raw, null, 2)
      : String(raw || "");

    const parsed = buildExecutionLogs(contentStr, defaultType);

    // [FIX] Fallback for non-empty content that failed to parse into meaningful chunks
    if (parsed.length === 0 && contentStr.trim().length > 0) {
      return [{
        id: `fallback-${contentStr.length}`, // Deterministic ID based on content
        type: defaultType,
        content: contentStr,
        timestamp: 0 // Static timestamp for fallback
      }];
    }

    return parsed;
  }, [block.content, block.tags]);

  return (
    <div className="h-64 md:h-80 border border-slate-200 rounded-lg overflow-hidden shadow-sm my-2">
      <SmartConsole logs={logs} className="h-full border-none rounded-none" />
    </div>
  );
};

// [FIX] Adapter: RenderAtomProps -> AtomInput Props
const AtomInputAdapter: React.FC<RenderAtomProps> = ({ block, state }) => {
  return <AtomInput block={block} isReadOnly={state.read_only} />;
};

const ROUTER: Partial<Record<RenderType, React.FC<RenderAtomProps>>> = {
  // Entities
  [RenderType.SCA_OPTION_CARD]: EntityScaCard,
  [RenderType.SCA_PLAN_CARD]: EntityScaPlanCard,
  [RenderType.AVL_CRITIQUE_CARD]: EntityAvlItem,
  [RenderType.VARL_ANALYSIS]: EntityVarlCard,
  [RenderType.RESULT_SUMMARY]: EntityResultCard,
  [RenderType.IDE_WORKSPACE]: EntityIdeWorkspace,

  // Atoms
  [RenderType.CODE_EDITOR]: AtomCode,
  [RenderType.MARKDOWN_VIEWER]: AtomText,
  [RenderType.DATA_VIEWER]: AtomData,
  [RenderType.ARTIFACT_GALLERY]: AtomArtifacts,
  [RenderType.LOG_CONSOLE]: AtomSmartConsoleAdapter, // [FIX] Route activated
  [RenderType.INPUT_TEXT]: AtomInputAdapter,

  // Layouts (Explicit Routing)
  [RenderType.CONTAINER_STACK]: StackLayout,
  [RenderType.CONTAINER_GRID]: GridLayout,
  [RenderType.CONTAINER_TABS]: TabsLayout,
  [RenderType.CONTAINER_SPLIT]: SplitLayout,
};

export function getWidgetComponent(block: { render_type?: RenderType; type: BlockType; tags?: string[] }): React.FC<RenderAtomProps> {
  if (block.render_type && ROUTER[block.render_type]) {
    return ROUTER[block.render_type]!;
  }

  // [FIX] Fallback Logic based on Tags
  const tags = block.tags || [];
  if (tags.includes("execution_logs") || tags.includes("stdout") || tags.includes("stderr")) {
    return AtomSmartConsoleAdapter;
  }

  // Standard Type Fallback
  switch (block.type) {
    case BlockType.FILE: return AtomArtifacts; // [FIX] Ensure FILE maps to Artifacts
    case BlockType.CONTAINER: return StackLayout;
    case BlockType.CODE: return AtomCode;
    case BlockType.DATA: return AtomData;
    default: return AtomText;
  }
}
