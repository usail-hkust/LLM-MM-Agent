"use client";
import { useMemo, useEffect } from "react";
import { useAuth } from "@/app/context/AuthContext";
import { useNodeWorkspace, useSubmitInteraction } from "@/app/lib/queries";
import { useIntentDispatcher } from "@/app/hooks/useIntentDispatcher";
import { NodeProvider } from "@/app/context/NodeContext";
import { LayoutMode, WorkflowStatus, ActionType } from "@/app/api/enums";
import { UnifiedDock } from "./layout/UnifiedDock";
import { UnifiedStageLayout } from "./layouts/UnifiedStageLayout";
import { Loader2, Box, AlertCircle, Lock, RotateCcw, Hourglass } from "lucide-react";
import { EmptyState, AgentProgress } from "@/app/components/shared/EmptyState";
import { ErrorBoundary } from "@/app/components/shared/ErrorBoundary";
import { useStageStore } from "@/lib/stores";
import { StageFormWrapper } from "@/app/components/stage/StageFormWrapper";
import { useUnifiedTimeline } from "@/app/hooks/useUnifiedTimeline";
import { useUI } from "@/app/hooks/useUI";
import { useDockActions } from "@/app/hooks/useDockActions";
import { RenderAction } from "@/app/api/schemas";
import { apiClient } from "@/app/lib/api-client";
import { AgentProgressPanel } from "./AgentProgressPanel";

export function Viewport({ projectId, nodeId, pendingInteraction }: { projectId: string; nodeId: string | null; pendingInteraction?: any }) {
  const { selectedVersionIndex, isAgentWorking, setAgentWorking, setNodeStatus, setNodeType } = useStageStore();
  const { toast } = useUI();
  const { token } = useAuth();

  // [FIX] Pass isAgentWorking to force polling
  const { data: workspaceData, isLoading, error } = useNodeWorkspace(projectId, nodeId, { isAgentWorking });

  // [NEW] Update store with node status and type when data changes
  useEffect(() => {
    if (workspaceData) {
      setNodeStatus(workspaceData.state?.status);
      setNodeType(workspaceData.definition?.type);
    }
  }, [workspaceData, setNodeStatus, setNodeType]);

  // [FIX] Lifecycle Management for isAgentWorking
  useEffect(() => {
    if (!workspaceData?.state) return;
    const s = workspaceData.state.status;
    if (isAgentWorking && (s === WorkflowStatus.DRAFTING || s === WorkflowStatus.FAILED || s === WorkflowStatus.COMMITTED || s === WorkflowStatus.REVIEWING)) {
      setAgentWorking(false);
    }
  }, [workspaceData, isAgentWorking, setAgentWorking]);

  // [Timeline Hook]
  const { timeline, effectiveVersion, refresh } = useUnifiedTimeline(projectId, nodeId, selectedVersionIndex, pendingInteraction);

  // [Actions]
  const { dispatch, pendingActionId } = useIntentDispatcher(projectId, nodeId);
  const submit = useSubmitInteraction(projectId, nodeId);

  // [CRITICAL FIX] Data Continuity Strategy (The "Dock Saver")
  const dockVersion = useMemo(() => {
    if (effectiveVersion) return effectiveVersion;
    
    if (workspaceData?.state) {
        return {
            id: "synthetic-head",
            node_id: nodeId!,
            version_index: timeline.length > 0 ? timeline[timeline.length - 1].version_index : 1,
            timestamp: new Date().toISOString(),
            status: workspaceData.state.status,
            status_override: isAgentWorking ? "RUNNING" : undefined,
            trigger: "CURRENT",
            data: { blocks: workspaceData.state.blocks },
            artifacts: [],
            permissions: {},
            is_live: true
        } as any; 
    }
    return null;
  }, [effectiveVersion, workspaceData, nodeId, timeline, isAgentWorking]);

  // [FIX] Ensure Timeline isn't empty for the Dock Rail
  const dockTimeline = useMemo(() => {
      if (timeline.length > 0) return timeline;
      if (dockVersion) return [dockVersion];
      return [];
  }, [timeline, dockVersion]);

  // [State Logic] Use Live Data?
  const useLiveData = !selectedVersionIndex || dockVersion?.is_live;

  // [State Logic] Is Active Version?
  const isActiveVersion = useMemo(() => {
    if (selectedVersionIndex === null) return true;
    if (!dockVersion || !workspaceData?.state) return false;
    const currentActiveId = workspaceData.state.active_version_id;
    if (dockVersion.is_live) return true;
    return dockVersion.id === currentActiveId;
  }, [dockVersion, workspaceData, selectedVersionIndex]);

  // [State Logic] Form Source
  const formSourceVersion = useMemo(() => {
    if (useLiveData && workspaceData?.state) {
      return {
        id: `live-workspace-${Date.now()}`,
        version_index: -1,
        data: { blocks: workspaceData.state.blocks }
      };
    }
    return dockVersion;
  }, [useLiveData, workspaceData, dockVersion]);

  // Active State Resolution Strategy
  const activeState = useMemo(() => {
    if (!dockVersion) return workspaceData?.state;

    const realStatus = workspaceData?.state?.status || dockVersion.status_override;
    const effectiveStatus = (isAgentWorking && realStatus !== "DRAFTING" && realStatus !== "RUNNING")
      ? "RUNNING" 
      : realStatus;

    if (useLiveData && workspaceData?.state) {
      return { ...workspaceData.state, status: effectiveStatus };
    }

    return {
      status: dockVersion.status,
      layout_mode: workspaceData?.state?.layout_mode || LayoutMode.STANDARD,
      is_read_only: true,
      blocks: dockVersion.data?.blocks || workspaceData?.state?.blocks || [],
      global_actions: []
    };
  }, [dockVersion, workspaceData, useLiveData, isAgentWorking]);

  const status = activeState?.status;
  const isLocked = status === WorkflowStatus.LOCKED;
  const isWaiting = [WorkflowStatus.VOID, WorkflowStatus.LOCKED].includes(status as any);

  const combinedGlobalActions = useMemo(() => {
    const actions: RenderAction[] = [];

    if (status === WorkflowStatus.FAILED && !activeState?.is_read_only) {
      actions.push({
        id: "sys_reset_node", label: "Reset & Retry", type: ActionType.DANGER, icon: "RotateCcw",
        payload: { action: "reset", run_after_reset: true }, confirm_message: "Hard reset this node? This will wipe all history.", validation_rule: "always_enabled", scope: "WORKSPACE"
      });
    }

    const backendGlobals = workspaceData?.state?.global_actions || [];
    const existingIds = new Set(actions.map(a => a.id));
    backendGlobals.forEach((a: any) => {
      if (!existingIds.has(a.id)) actions.push(a);
    });

    return actions;
  }, [status, activeState?.is_read_only, workspaceData?.state?.global_actions]);

  useDockActions(combinedGlobalActions, dispatch, !!pendingActionId || submit.isPending || isAgentWorking, status);

  if (!nodeId) return <EmptyState icon={Box} title="No Selection" description="Select a node." />;
  if (isLoading) return <div className="h-full flex items-center justify-center text-slate-400 gap-2"><Loader2 className="w-8 h-8 animate-spin" />Loading...</div>;
  if (error) return <div className="h-full flex items-center justify-center text-red-500 gap-2"><AlertCircle /> Load Failed</div>;

  let modeStr = "standard";
  if (activeState?.layout_mode === LayoutMode.FOCUS) modeStr = "focus";
  else if (activeState?.layout_mode === LayoutMode.WORKBENCH) modeStr = "workbench";
  else if (activeState?.layout_mode === LayoutMode.SELECTION) modeStr = "selection";
  else if (activeState?.layout_mode === LayoutMode.DOCUMENT) modeStr = "document";

  // [FIX] Empty State Logic
  const hasBlocks = (activeState?.blocks?.length || 0) > 0;
  const isRefining = (status === "DRAFTING" || status === "RUNNING") && hasBlocks;
  const showEmptyState = (!hasBlocks && !combinedGlobalActions.length) || (isWaiting && !isRefining);

  // [FIX] Determine Empty State UI
  let emptyIcon = Box;
  let emptyTitle = "Ready";
  let emptyDesc = "Node initialized.";

  if (isLocked) {
    emptyIcon = Lock;
    emptyTitle = "Pending Dependencies";
    emptyDesc = "This node is waiting for upstream tasks to complete.";
  } else if (status === "DRAFTING") {
    emptyIcon = Loader2;
    emptyTitle = "Agent Working...";
    emptyDesc = "The AI is currently generating content for this step.";
  } else if (status === WorkflowStatus.FAILED) {
    emptyIcon = AlertCircle;
    emptyTitle = "Execution Failed";
    const rawError = workspaceData?.state?.metadata?.system_error;
    emptyDesc = typeof rawError === "string" ? rawError : (rawError ? JSON.stringify(rawError) : "An unexpected error occurred.");
  } else if (status === WorkflowStatus.VOID) {
    emptyIcon = Hourglass;
    emptyTitle = "Waiting for Pipeline";
    emptyDesc = "This node will start automatically when the workflow reaches it.";
  }

  return (
    <NodeProvider value={{ projectId, nodeId, isReadOnly: activeState?.is_read_only ?? true }}>
      <ErrorBoundary>
        <StageFormWrapper version={formSourceVersion}>
          <div className="relative h-full flex flex-col bg-slate-50/30 overflow-hidden">

            {/* 实时工作进展显示面板 */}
            <AgentProgressPanel />

            <div className="flex-1 overflow-hidden relative z-0">
              {showEmptyState ? (
                status === "DRAFTING" ? (
                  <AgentProgress
                    title={emptyTitle}
                    description={emptyDesc}
                  />
                ) : (
                  <EmptyState
                    icon={emptyIcon}
                    title={emptyTitle}
                    description={emptyDesc}
                    action={status === WorkflowStatus.FAILED ? (
                      <button onClick={async () => {
                        try {
                          setAgentWorking(true);
                          await apiClient(`/projects/${projectId}/nodes/${nodeId}/interaction`, token, {
                            method: "POST",
                            body: JSON.stringify({ action: "reset", node_id: nodeId, payload: { run_after_reset: true } })
                          });
                          refresh();
                          toast.success("Reset triggered. Auto-execution should restart.");
                        } catch (e: any) {
                          setAgentWorking(false);
                          toast.error(e.message || "Reset failed");
                        }
                      }} className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors shadow-sm">
                        <RotateCcw className="w-4 h-4" />
                        Reset & Retry
                      </button>
                    ) : null}
                  />
                )
              ) : (
                <UnifiedStageLayout
                  mode={modeStr}
                  nodeType={workspaceData?.definition?.type}
                  blocks={activeState?.blocks || []}
                  isReadOnly={activeState?.is_read_only ?? true}
                  onAction={dispatch}
                  isSubmitting={!!pendingActionId}
                  status={status}
                />
              )}
            </div>

            {/* Render UnifiedDock conditionally based on robust 'dockVersion' */}
            {dockVersion && (
              <UnifiedDock
                projectId={projectId}
                nodeId={nodeId!} 
                timeline={dockTimeline}
                version={dockVersion}
                nodeState={workspaceData?.state}
                isActiveVersion={isActiveVersion}
                onRefresh={refresh}
                onAction={dispatch}
                pendingActionId={pendingActionId}
              />
            )}
          </div>
        </StageFormWrapper>
      </ErrorBoundary>
    </NodeProvider>
  );
}
