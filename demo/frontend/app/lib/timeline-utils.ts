import {
  InteractionRequest,
  NodeExecutionState,
  HistoryVersion,
  UnifiedHistoryEntry,
  DEFAULT_PERMISSIONS,
  WorkflowStatus,
} from "@/app/types";

/**
 * [Pure Function]
 * Merges history timeline with real-time state to generate final timeline array.
 * [REFACTORED] Simplified - no nested merging, just direct appending.
 */
export function mergeTimelineData(
  historyTimeline: UnifiedHistoryEntry[] | undefined, // From backend NodeHistoryResponse.timeline
  pendingInteraction: InteractionRequest | null | undefined,
  runningNode: NodeExecutionState | undefined,
  targetNodeId: string | null
): HistoryVersion[] {
  if (!targetNodeId) return [];
  const rawTimeline = historyTimeline || [];

  const baseTimeline: HistoryVersion[] = rawTimeline.map((entry) => ({
    ...entry,
    node_id: targetNodeId,
    permissions: entry.permissions || DEFAULT_PERMISSIONS,
    artifacts: entry.artifacts || [],
  }));

  const lastVersion = baseTimeline.length > 0 ? baseTimeline[baseTimeline.length - 1] : null;
  const nextIndex = (lastVersion?.version_index ?? -1) + 1;

  // Inject Speculative "Next Version" for UI feedback (Loading/Input)
  if (pendingInteraction && pendingInteraction.node_id === targetNodeId) {
    // If we have a pending interaction but the history explicitly says we are COMMITTED, 
    // it means we haven't refreshed yet, or it's a new prompt.
    // But usually, if status is REVIEWING, it matches the last history item.
    const isAlreadyInHistory = lastVersion && lastVersion.status === "REVIEWING";
    
    if (!isAlreadyInHistory) {
         const rawPayload = pendingInteraction.payload || {};
         baseTimeline.push({
            id: "live-interaction",
            node_id: targetNodeId,
            version_index: nextIndex,
            timestamp: new Date().toISOString(),
            status: "RUNNING",
            status_override: "AWAITING_HUMAN_INPUT",
            is_live: true,
            trigger: "INTERACTION",
            data: rawPayload.pattern_state || {},
            permissions: DEFAULT_PERMISSIONS,
            artifacts: [],
         } as any);
    }
  }
  else if (runningNode && runningNode.effective_id === targetNodeId && runningNode.status === WorkflowStatus.DRAFTING) {
     // Inject Running Placeholder
     const isRunningInHistory = lastVersion && lastVersion.status === "RUNNING"; 
     if (!isRunningInHistory) {
        baseTimeline.push({
            id: "live-running",
            node_id: targetNodeId,
            version_index: nextIndex,
            timestamp: new Date().toISOString(),
            status: "RUNNING",
            status_override: "RUNNING",
            trigger: "RUN",
            data: {},
            permissions: DEFAULT_PERMISSIONS,
            artifacts: [],
            is_live: true
        } as any);
     }
  }

  return baseTimeline.sort((a, b) => a.version_index - b.version_index);
}
