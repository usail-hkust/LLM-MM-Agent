"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { WorkflowStatus } from "@/app/api/enums";
import { useProgress } from "@/app/context/ProgressContext";

interface ProgressInferenceOptions {
  nodeId: string | null;
  nodeStatus?: WorkflowStatus | string;
  nodeType?: string;
  isEnabled: boolean;
}

/**
 * 智能进度推断 Hook
 * 当后端没有发送详细的 SSE 进度事件时，根据节点状态自动推断进度
 */
export function useAgentProgressInference({
  nodeId,
  nodeStatus,
  nodeType,
  isEnabled,
}: ProgressInferenceOptions) {
  const { startProgress, updateProgress, nextStep, completeProgress, resetProgress, progress } = useProgress();

  // 状态追踪
  const startTimeRef = useRef<number | null>(null);
  const lastStatusRef = useRef<string | undefined>(nodeStatus);
  const [inferredPercentage, setInferredPercentage] = useState(0);
  const [currentMessage, setCurrentMessage] = useState("");

  // 根据节点类型生成有意义的进度消息
  const getProgressMessage = useCallback((status: string | undefined, percentage: number, type?: string) => {
    const typeUpper = type?.toUpperCase() || "";

    // Executor 类型节点的消息
    if (typeUpper.includes("EXECUTOR") || typeUpper.includes("CODE_GENERATOR")) {
      if (percentage < 20) return "正在分析需求...";
      if (percentage < 40) return "正在生成代码框架...";
      if (percentage < 60) return "正在编写实现代码...";
      if (percentage < 80) return "正在优化代码逻辑...";
      if (percentage < 90) return "正在添加注释和文档...";
      return "正在完成最终检查...";
    }

    // 数据分析节点
    if (typeUpper.includes("ANALYSIS") || typeUpper.includes("DATA")) {
      if (percentage < 30) return "正在加载数据...";
      if (percentage < 50) return "正在探索数据特征...";
      if (percentage < 70) return "正在执行分析算法...";
      if (percentage < 90) return "正在生成可视化结果...";
      return "正在整理分析报告...";
    }

    // 默认通用消息
    const statusUpper = (status || "").toUpperCase();
    if (statusUpper === "DRAFTING") {
      if (percentage < 25) return "正在理解任务需求...";
      if (percentage < 50) return "正在生成内容草稿...";
      if (percentage < 75) return "正在优化生成结果...";
      return "正在进行最终审查...";
    }
    if (statusUpper === "REVIEWING") {
      return "正在等待人工审核...";
    }
    if (statusUpper === "COMMITTED") {
      return "已完成！";
    }
    if (statusUpper === "FAILED") {
      return "执行失败";
    }
    return "正在处理...";
  }, []);

  // 根据节点类型推断总步骤数
  const inferTotalSteps = useCallback((type?: string): number => {
    const typeUpper = type?.toUpperCase() || "";

    if (typeUpper.includes("EXECUTOR") || typeUpper.includes("CODE_GENERATOR")) {
      return 10; // 代码生成通常有更多步骤
    }
    if (typeUpper.includes("ANALYSIS") || typeUpper.includes("DATA")) {
      return 8;
    }
    return 6; // 默认步骤数
  }, []);

  // 计算预估剩余时间（基于历史数据）
  const estimateTimeRemaining = useCallback((percentage: number, elapsed: number): number | null => {
    if (percentage <= 0 || elapsed < 1000) return null;

    // 简单线性估算
    const totalTimeEstimated = (elapsed / percentage) * 100;
    const remaining = Math.max(0, totalTimeEstimated - elapsed);

    return Math.round(remaining);
  }, []);

  // 启动进度追踪
  useEffect(() => {
    const statusUpper = (nodeStatus || "").toUpperCase();

    console.log("[ProgressInference] State check:", {
      isEnabled,
      nodeId,
      nodeStatus,
      statusUpper,
      lastStatus: lastStatusRef.current,
    });

    if (!isEnabled || !nodeId || statusUpper !== "DRAFTING") {
      if (startTimeRef.current && (statusUpper === "COMMITTED")) {
        completeProgress(getProgressMessage(nodeStatus, 100, nodeType));
        startTimeRef.current = null;
      }
      return;
    }

    // 状态从非 DRAFTING 变为 DRAFTING，开始新的进度追踪
    if ((lastStatusRef.current || "").toUpperCase() !== "DRAFTING" && statusUpper === "DRAFTING") {
      console.log("[ProgressInference] Starting progress tracking");
      startTimeRef.current = Date.now();
      const totalSteps = inferTotalSteps(nodeType);

      startProgress(nodeId, "Agent Working...", "percentage", totalSteps);
      setInferredPercentage(0);
      setCurrentMessage(getProgressMessage(nodeStatus, 0, nodeType));
    }

    lastStatusRef.current = nodeStatus;
  }, [nodeId, nodeStatus, isEnabled, nodeType, startProgress, completeProgress, inferTotalSteps, getProgressMessage]);

  // 模拟进度更新（每秒更新一次）
  useEffect(() => {
    const statusUpper = (nodeStatus || "").toUpperCase();
    if (!isEnabled || !nodeId || statusUpper !== "DRAFTING" || !startTimeRef.current) {
      return;
    }

    console.log("[ProgressInference] Starting progress update interval");

    const interval = setInterval(() => {
      const elapsed = Date.now() - (startTimeRef.current || 0);
      const totalSteps = inferTotalSteps(nodeType);

      // 基于时间的进度估算（假设总时长根据节点类型不同）
      const estimatedDuration = totalSteps * 10000; // 每步大约10秒
      let percentage = Math.min(95, Math.floor((elapsed / estimatedDuration) * 100));

      console.log("[ProgressInference] Updating progress:", {
        elapsed,
        percentage,
        totalSteps,
      });

      // 确保进度只增不减
      setInferredPercentage((prev) => {
        const newPercentage = Math.max(prev, percentage);
        const message = getProgressMessage(nodeStatus, newPercentage, nodeType);
        const timeRemaining = estimateTimeRemaining(newPercentage, elapsed);

        console.log("[ProgressInference] Calling updateProgress:", {
          newPercentage,
          message,
          timeRemaining,
        });

        // 更新进度上下文
        updateProgress({
          percentage: newPercentage,
          message,
          currentStep: Math.floor((newPercentage / 100) * totalSteps),
          estimatedTimeRemaining: timeRemaining,
        });

        setCurrentMessage(message);
        return newPercentage;
      });
    }, 1000);

    return () => {
      console.log("[ProgressInference] Clearing interval");
      clearInterval(interval);
    };
  }, [nodeId, nodeStatus, isEnabled, nodeType, inferTotalSteps, getProgressMessage, estimateTimeRemaining, updateProgress]);

  // 状态变化时的处理
  useEffect(() => {
    if (!isEnabled || !nodeId) return;

    // REVIEWING 状态
    if (nodeStatus === WorkflowStatus.REVIEWING && lastStatusRef.current !== WorkflowStatus.REVIEWING) {
      updateProgress({
        percentage: 95,
        message: getProgressMessage(nodeStatus, 95, nodeType),
        currentStep: inferTotalSteps(nodeType) - 1,
      });
      lastStatusRef.current = nodeStatus;
    }

    // COMPLETED 状态
    if (nodeStatus === WorkflowStatus.COMMITTED) {
      if (progress?.status === "running") {
        completeProgress(getProgressMessage(WorkflowStatus.COMMITTED, 100, nodeType));
        startTimeRef.current = null;
      }
      lastStatusRef.current = nodeStatus;
    }

    // FAILED 状态
    if (nodeStatus === WorkflowStatus.FAILED) {
      if (progress?.status === "running") {
        completeProgress("执行失败，请查看错误信息");
        startTimeRef.current = null;
      }
      lastStatusRef.current = nodeStatus;
    }
  }, [nodeId, nodeStatus, isEnabled, nodeType, progress, completeProgress, updateProgress, getProgressMessage, inferTotalSteps]);

  // 清理
  useEffect(() => {
    return () => {
      if (!isEnabled && progress?.status === "running") {
        resetProgress();
      }
    };
  }, [isEnabled, progress, resetProgress]);

  return {
    inferredPercentage,
    currentMessage,
    isInferring: isEnabled && nodeStatus === WorkflowStatus.DRAFTING && !!progress,
  };
}
