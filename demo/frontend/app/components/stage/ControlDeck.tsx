"use client";

import { cn } from "@/lib/utils";
import { GitBranch, RotateCcw, AlertOctagon, CornerUpLeft } from "lucide-react";
import { useStageStore } from "@/lib/stores";
import { useUI } from "@/app/hooks/useUI";
import { useForkNode, useRestoreNodeVersion, useSubmitInteraction } from "@/app/lib/queries";

interface ControlDeckProps {
  projectId: string;
  nodeId: string; // [FIX] Explicit nodeId required
  nodeState: any; // Flexible type to handle both frontend/backend shapes
  effectiveVersionIndex: number;
  isActiveVersion?: boolean;
  isPhantom?: boolean; // [NEW] Indicates a non-persisted version
  onRefresh: () => void;
}

export function ControlDeck({
  projectId,
  nodeId,
  nodeState,
  effectiveVersionIndex,
  isActiveVersion = false,
  isPhantom = false,
  onRefresh,
}: ControlDeckProps) {
  const { selectedArtifactId, selectNode, setAgentWorking } = useStageStore();
  const { dialog, toast } = useUI();
  const restoreMutation = useRestoreNodeVersion(projectId);
  const forkMutation = useForkNode(projectId);
  const submitMutation = useSubmitInteraction(projectId, nodeId);
  const isMutating = restoreMutation.isPending || forkMutation.isPending || submitMutation.isPending;

  // [FIX]: Remove the `!isHead` check.
  // We allow forking a specific step (artifact) even if we are currently at the HEAD version.
  const isArtifactFork = !!(selectedArtifactId && selectedArtifactId !== "FINAL_OUTPUT");

  // [FIX] Derive locked state robustly
  // Backend returns NodeStateView which has 'status', not 'is_locked'
  const isLocked = nodeState?.is_locked || nodeState?.status === "LOCKED";

  const handleRestore = async () => {
    // Cannot restore to a phantom version or if already viewing the active version
    if (isActiveVersion || isPhantom) return;

    const confirm = await dialog.confirm("Revert node state to this version?", {
      title: `Restore v${effectiveVersionIndex}`,
      confirmText: "Restore Snapshot",
      cancelText: "Cancel",
    });
    if (!confirm || isArtifactFork) return;

    try {
      await restoreMutation.mutateAsync({
        effectiveNodeId: nodeId, // [FIX] Use prop ID, NOT nodeState.effective_id
        versionIndex: effectiveVersionIndex,
      });
      toast.success(`Successfully restored v${effectiveVersionIndex}`);

      onRefresh();
      // [FIX] Stay on the restored version to avoid confusion (seeing "v4" immediately).
      // The user can manually click "Go to Live" via the Beacon to start editing the restored state.
      // selectNode(nodeId);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      toast.error(message);
    }
  };

  const handleFork = async () => {
    if (effectiveVersionIndex < 0 || isPhantom) return;

    const title = isArtifactFork ? "Fork from Intermediate Step" : `Fork from Version ${effectiveVersionIndex}`;
    const msg = isArtifactFork
      ? "Create a new branch starting EXACTLY from this intermediate step (Draft/Option)?"
      : `Start a NEW session based on the output of Version ${effectiveVersionIndex}?`;

    const confirm = await dialog.confirm(msg, { title });
    if (!confirm) return;

    try {
      await forkMutation.mutateAsync({
        effectiveNodeId: nodeId, // [FIX] Use prop ID
        baseVersionIndex: effectiveVersionIndex,
        targetArtifactId: isArtifactFork ? selectedArtifactId : null,
      });
      toast.success("Branch created successfully.");
      selectNode(nodeId);
      onRefresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      toast.error(message);
    }
  };

  const handleRun = async () => {
    try {
      await submitMutation.mutateAsync({ action: "run_node", payload: { intent: "generate" } });
      toast.success("Execution started");
      onRefresh();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      toast.error(message);
    }
  };

  const handleReset = async () => {
    const confirm = await dialog.confirm("Reset this node and re-execute from scratch?", {
      title: "Reset Node",
      danger: true,
      confirmText: "Reset & Run",
    });
    if (!confirm) return;

    try {
      // [OPTIMISTIC UI] Force UI into running state immediately
      setAgentWorking(true);

      await submitMutation.mutateAsync({
        action: "reset",
        payload: { run_after_reset: true }
      });
      toast.success("Node reset and execution started.");
      onRefresh();
      selectNode(nodeId);
    } catch (e) {
      setAgentWorking(false);
      const message = e instanceof Error ? e.message : String(e);
      toast.error(message);
    }
  };

  const btnBase =
    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <div className="flex items-center gap-2">
      {isActiveVersion ? (
        !isLocked && (
          <div className="flex items-center gap-2">
            {(nodeState.status === "VOID" || nodeState.status === "CREATED") && (
              <button
                onClick={handleRun}
                disabled={isMutating}
                className={cn(btnBase, "text-white bg-blue-600 hover:bg-blue-700")}
              >
                <CornerUpLeft className="w-3.5 h-3.5 rotate-180" />
                Run Now
              </button>
            )}
            <button
              onClick={handleReset}
              disabled={isMutating}
              className={cn(btnBase, "text-red-600 bg-white border border-red-200 hover:bg-red-50")}
              title="Clear all history for this node and run again"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Node
            </button>
          </div>
        )
      ) : (
        <>
          {!isLocked && (
            <button
              onClick={handleRestore}
              disabled={isMutating || isArtifactFork || isPhantom}
              className={cn(
                btnBase,
                isArtifactFork
                  ? "text-slate-300 border-slate-100 bg-slate-50"
                  : "text-amber-800 bg-white border-amber-200 hover:bg-amber-50",
              )}
              title={isArtifactFork ? "Cannot restore from a partial artifact" : "Revert node to this snapshot"}
            >
              <CornerUpLeft className="w-3.5 h-3.5" />
              Restore
            </button>
          )}
        </>
      )}

      <button
        onClick={handleFork}
        // Disable fork if node is locked OR if this is a phantom version (not yet persisted)
        disabled={isMutating || isLocked || isPhantom}
        className={cn(
          btnBase,
          isArtifactFork ? "bg-purple-600 text-white hover:bg-purple-700" : "bg-slate-900 text-white hover:bg-slate-700",
        )}
        title={
          isPhantom
            ? "Cannot fork a pending execution step"
            : isArtifactFork
              ? "Create new branch from this artifact"
              : `Create new branch from Version ${effectiveVersionIndex}`
        }
      >
        {isArtifactFork ? <AlertOctagon className="w-3.5 h-3.5" /> : <GitBranch className="w-3.5 h-3.5" />}
        {isArtifactFork ? "Fork Step" : `Fork v${String(effectiveVersionIndex)}`}
      </button>
    </div>
  );
}
