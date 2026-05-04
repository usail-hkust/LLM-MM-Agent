"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSubmitInteraction } from "@/app/lib/queries";
import { useUI } from "@/app/hooks/useUI";
import { RenderAction, ActionType } from "@/app/api/schemas";
import { WorkflowStatus } from "@/app/api/enums";
import { useStageStore } from "@/lib/stores";

export function useIntentDispatcher(projectId: string, nodeId: string | null) {
  const { toast, dialog } = useUI();
  const queryClient = useQueryClient(); // [FIX] 引入 QueryClient 用于乐观更新
  const submit = useSubmitInteraction(projectId, nodeId);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const { setAgentWorking } = useStageStore();

  /**
   * [FIX] 破坏性乐观更新策略
   * 点击后立即清空动作集，物理移除按钮，杜绝重复提交
   */
  const handleActionFeedback = (verb: string, payload: Record<string, any> = {}) => {
    const optimisticUpdateStatus = (newStatus: WorkflowStatus, clearActions = false) => {
      if (!nodeId) return;
      const queryKey = ["projects", projectId, "nodes", nodeId, "workspace"];

      queryClient.setQueryData(queryKey, (oldData: any) => {
        if (!oldData || !oldData.state) return oldData;

        const isSystemWorking = newStatus === WorkflowStatus.DRAFTING;

        return {
          ...oldData,
          state: {
            ...oldData.state,
            status: newStatus,
            // 立即锁定编辑器
            is_read_only: isSystemWorking ? true : oldData.state.is_read_only,
            // [CRITICAL FIX] 强制清空动作列表
            // 即使后台任务还在排队，UI 上按钮直接消失
            global_actions: clearActions ? [] : oldData.state.global_actions,
            allowed_actions: clearActions ? [] : oldData.state.allowed_actions
          }
        };
      });
    };

    switch (verb) {
      // --- 异步触发类 ---
      case "reject_node":
      case "refine_node":
        toast.info("Refinement initiated. Agent is working...");
        // 传入 true，强制清空按钮
        optimisticUpdateStatus(WorkflowStatus.DRAFTING, true);
        setAgentWorking(true);
        break;

      case "run_node":
        toast.info("Execution started...");
        optimisticUpdateStatus(WorkflowStatus.DRAFTING, true);
        setAgentWorking(true);
        break;

      // --- 同步完成类 ---
      case "approve_node":
      case "select_and_commit":
        toast.success("Node approved successfully.");
        optimisticUpdateStatus(WorkflowStatus.COMMITTED);
        break;

      case "reset":
        toast.success("Node has been reset.");
        optimisticUpdateStatus(WorkflowStatus.VOID);
        if (payload.run_after_reset) {
          setAgentWorking(true);
        }
        break;

      case "fork_node":
        toast.success("New branch created.");
        optimisticUpdateStatus(WorkflowStatus.REVIEWING);
        break;

      case "restore_node":
        toast.success("Snapshot restored.");
        optimisticUpdateStatus(WorkflowStatus.COMMITTED);
        break;

      case "select_option":
        toast.success("Option selected.");
        break;

      case "save_draft":
        break;

      default:
        toast.success("Action request accepted.");
    }
  };

  const dispatch = async (action: RenderAction, extraPayload: Record<string, any> = {}) => {
    if (!nodeId) return;
    let dynamicInputs: Record<string, any> = {};

    // Input Spec 处理逻辑保持不变
    if (action.input_spec) {
      const { type, label, key, required, default_value, options } = action.input_spec;
      const res = await dialog.prompt(label, {
        title: action.label,
        required: required !== false,
        defaultValue: default_value || "",
        danger: action.type === ActionType.DANGER,
        inputType: type as any,
        options: options
      });
      if (res === null) return;
      dynamicInputs = { [key]: res };
    } else if (action.confirm_message) {
      if (!await dialog.confirm(action.confirm_message, { title: action.label, danger: action.type === ActionType.DANGER })) return;
    }

    setPendingId(action.id);
    try {
      const rawPayload = action.payload || {};
      const verb = rawPayload.action || action.id;
      const { action: _, ...staticData } = rawPayload;

      // [FIX] 应用破坏性乐观更新 - 移动到提交前，确保立即锁定 UI
      handleActionFeedback(verb, staticData);

      await submit.mutateAsync({ action: verb, payload: { ...staticData, ...extraPayload, ...dynamicInputs } });

    } catch (e: any) {
      toast.error(e.message || "Action failed");
      setAgentWorking(false); // [FIX] Release lock on error
    } finally {
      setPendingId(null);
      // [FIX] Do NOT clear agentWorking here. 
      // We rely on the Viewport to detect the status change (to DRAFTING/RUNNING) 
      // and THEN clear the flag, or clear it if an error occurred.
      // However, on error (catch block), we might want to clear it? 
      // Actually, if error occurs, we should clear it. 
      // If success, we LEAVE IT TRUE so Viewport can bridge the gap.
    }
  };

  return { dispatch, pendingActionId: pendingId };
}
