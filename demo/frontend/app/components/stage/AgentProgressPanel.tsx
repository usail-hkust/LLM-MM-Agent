"use client";

import { useProgress } from "@/app/context/ProgressContext";
import { useStageStore } from "@/lib/stores";
import { useEffect } from "react";
import { useSignal } from "@/app/context/SignalContext";
import { useAgentProgressInference } from "@/app/hooks/useAgentProgressInference";

export function AgentProgressPanel() {
  const { isAgentWorking, selectedNodeId, selectedNodeStatus, selectedNodeType } = useStageStore();
  const { progress, startProgress, updateProgress, nextStep, completeProgress, startAutoProgress } = useProgress();
  const { on } = useSignal();

  console.log("[AgentProgressPanel] Render:", {
    isAgentWorking,
    selectedNodeId,
    selectedNodeStatus,
    selectedNodeType,
    hasProgress: !!progress,
    progress: progress ? {
      title: progress.title,
      percentage: progress.percentage,
      message: progress.message,
      currentStep: progress.currentStep,
      totalSteps: progress.totalSteps,
    } : null,
  });

  // [NEW] 直接使用自动进度，不依赖智能推断系统
  useEffect(() => {
    if (isAgentWorking && !progress && selectedNodeId) {
      console.log("[AgentProgressPanel] Starting auto progress");
      const totalSteps = selectedNodeType?.includes("EXECUTOR") || selectedNodeType?.includes("CODE") ? 10 : 6;
      startAutoProgress("Agent Working...", totalSteps);
    }

    // 当停止工作时，完成进度
    if (!isAgentWorking && progress && progress.status === "running") {
      console.log("[AgentProgressPanel] Agent stopped, completing progress");
      completeProgress("执行完成！");
    }
  }, [isAgentWorking, progress, selectedNodeId, selectedNodeType, startAutoProgress, completeProgress]);

  // 使用智能进度推断系统（备用）
  useAgentProgressInference({
    nodeId: selectedNodeId,
    nodeStatus: selectedNodeStatus as any,
    nodeType: selectedNodeType,
    isEnabled: false, // 禁用智能推断，使用自动进度
  });

  // 监听 SSE 事件更新进度
  useEffect(() => {
    const unsubStart = on("agent_progress_start", (data: any) => {
      console.log("[AgentProgressPanel] SSE: agent_progress_start", data);
      startProgress(data.id || "agent", data.title || "Agent Working...", data.type || "percentage", data.totalSteps || 100);
    });

    const unsubUpdate = on("agent_progress", (data: any) => {
      console.log("[AgentProgressPanel] SSE: agent_progress", data);
      updateProgress({
        percentage: data.percentage,
        message: data.message || data.step,
        currentStep: data.currentStep,
      });
    });

    const unsubStep = on("agent_step", (data: any) => {
      console.log("[AgentProgressPanel] SSE: agent_step", data);
      nextStep(data.message || data.step);
    });

    const unsubComplete = on("agent_progress_complete", (data: any) => {
      console.log("[AgentProgressPanel] SSE: agent_progress_complete", data);
      completeProgress(data.message || "Completed!");
    });

    return () => {
      unsubStart();
      unsubUpdate();
      unsubStep();
      unsubComplete();
    };
  }, [on, startProgress, updateProgress, nextStep, completeProgress]);

  // 如果没有在工作，也不显示
  if (!isAgentWorking) return null;

  // 如果有进度数据，显示进度面板
  if (progress) {
    return (
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-white/95 backdrop-blur-sm border border-slate-200 rounded-xl shadow-lg px-4 py-3 min-w-[300px] max-w-md animate-fade-in-up">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-700">{progress.title || "Agent Progress"}</span>
          <span className="text-xs text-slate-500">{progress.percentage}%</span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-1.5 mb-2 overflow-hidden">
          <div 
            className="bg-blue-500 h-full rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress.percentage}%` }}
          />
        </div>
        <div className="text-xs text-slate-600 truncate">
          {progress.message || "Processing..."}
        </div>
        {progress.estimatedTimeRemaining !== null && progress.estimatedTimeRemaining > 0 && (
          <div className="text-xs text-slate-400 mt-1">
            Estimated: {Math.round(progress.estimatedTimeRemaining / 1000)}s remaining
          </div>
        )}
      </div>
    );
  }

  // 如果在工作但没有进度数据，显示简单的加载状态
  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-white/95 backdrop-blur-sm border border-slate-200 rounded-xl shadow-lg px-4 py-3 animate-fade-in-up">
      <div className="flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-bold text-slate-700">Agent Working...</span>
      </div>
    </div>
  );
}
