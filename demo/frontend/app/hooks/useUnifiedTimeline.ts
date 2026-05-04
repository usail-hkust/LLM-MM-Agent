"use client";
import { useMemo } from "react";
import { InteractionRequest } from "@/app/api/schemas";
import { useNodeHistory, useProjectDetail } from "@/app/lib/queries";
import { mergeTimelineData } from "@/app/lib/timeline-utils";

export function useUnifiedTimeline(
  projectId: string,
  nodeId: string | null,
  selectedVersionIndex: number | null,
  pendingInteraction?: InteractionRequest | null, // [FIX] Trust the prop
) {
  const { data: historyData, refetch, isLoading } = useNodeHistory(projectId, nodeId);
  const { data: projectData } = useProjectDetail(projectId);

  const nodeSignal = useMemo(() => {
    if (!nodeId || !projectData?.execution_topology) return undefined;
    for (const nodes of Object.values(projectData.execution_topology)) {
      // Guard: ensure nodes is an array before calling .find()
      if (!Array.isArray(nodes)) continue;
      const found = nodes.find((n) => n.effective_id === nodeId);
      if (found) return found;
    }
    return undefined;
  }, [nodeId, projectData]);

  const timeline = useMemo(() => {
    return mergeTimelineData(
      historyData?.timeline || [],
      pendingInteraction,
      nodeSignal,
      nodeId
    );
  }, [historyData, pendingInteraction, nodeSignal, nodeId]);

  const effectiveVersion = useMemo(() => {
    if (timeline.length === 0) return null;
    if (selectedVersionIndex === null) return timeline[timeline.length - 1];

    const found = timeline.find((v) => v.version_index === selectedVersionIndex);
    if (!found) {
      console.warn(`[useUnifiedTimeline] Requested version ${selectedVersionIndex} not found in timeline of length ${timeline.length}. Fallback to HEAD.`);
      return timeline[timeline.length - 1];
    }
    return found;
  }, [timeline, selectedVersionIndex]);

  return {
    timeline,
    effectiveVersion,
    status: isLoading ? "FETCHING" : "SYNCED",
    refresh: refetch
  };
}
