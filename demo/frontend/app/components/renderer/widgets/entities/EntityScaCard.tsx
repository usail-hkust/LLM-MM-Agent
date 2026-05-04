"use client";
import React from "react";
import { RenderAtomProps, BlockType } from "@/app/domain/abp"; // Ensure BlockType is imported
import { ScaOptionCard } from "@/app/components/stage/pure/ScaOptionCard";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { useScaSelectionContext } from "@/app/components/renderer/utils/sca-selection-context";

export const EntityScaCard: React.FC<RenderAtomProps> = (props) => {
  const { block, actions, onAction } = props;
  const { value } = useAtomBinding(props);
  const meta = block.meta || {};
  const scaContext = useScaSelectionContext();
  const isSelected = scaContext?.ignoreSelection ? false : meta.is_selected;
  
  // [FIX] Defensive Unwrap Logic
  let pureData: any = value || block.content || {};

  // 1. Handle nested "data" wrapper (Legacy API pattern)
  if ((pureData as any).data && typeof (pureData as any).data === 'object' && !(pureData as any).sub_problem_list) {
      pureData = (pureData as any).data;
  }

  // 2. Handle "blocks" wrapper (NodeOutput serialization pattern)
  // 如果收到的是 {"blocks": [...]}, 尝试从中提取第一个 DATA 块
  if (pureData.blocks && Array.isArray(pureData.blocks)) {
      const dataBlock = pureData.blocks.find((b: any) => b.type === "DATA" || b.type === "json");
      if (dataBlock && dataBlock.content) {
          pureData = dataBlock.content;
      }
  }

  const selectAction = actions.find(a => a.id === "select" || a.payload?.action === "select");
  const handleSelect = () => {
    scaContext?.markUserSelected();
    if (selectAction) onAction(selectAction);
  };

  return (
    <ScaOptionCard
      id={block.id}
      title={meta.title || block.label}
      description={meta.description}
      aiAnalysis={meta.ai_analysis}
      data={pureData as Record<string, any>}
      isManuallyEdited={meta.is_manually_edited}
      isSelected={isSelected}
      isRejected={meta.status === "REJECTED"}
      readOnly={props.state.read_only}
      onSelect={handleSelect}
    />
  );
};
