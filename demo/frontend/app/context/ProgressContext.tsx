"use client";

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";

// 进度类型定义
export type ProgressStatus = "idle" | "running" | "completed" | "error";
export type ProgressType = "linear" | "percentage" | "steps";

export interface ProgressStep {
  id: string;
  label: string;
  status: ProgressStatus;
  description?: string;
  startTime?: number;
  endTime?: number;
}

export interface ProgressState {
  id: string | null;
  title: string;
  type: ProgressType;
  status: ProgressStatus;
  currentStep: number;
  totalSteps: number;
  percentage: number;
  message: string;
  steps: ProgressStep[];
  startTime: number | null;
  estimatedTimeRemaining: number | null;
}

interface ProgressContextType {
  // 状态
  progress: ProgressState | null;
  isVisible: boolean;

  // Actions
  startProgress: (id: string, title: string, type: ProgressType, totalSteps?: number) => void;
  updateProgress: (data: Partial<ProgressState>) => void;
  nextStep: (message?: string) => void;
  completeProgress: (message?: string) => void;
  errorProgress: (error: string) => void;
  resetProgress: () => void;

  // UI
  show: () => void;
  hide: () => void;
  toggle: () => void;

  // [NEW] 自动更新进度
  startAutoProgress: (title: string, totalSteps?: number) => void;
}

const ProgressContext = createContext<ProgressContextType | null>(null);

export function useProgress() {
  const context = useContext(ProgressContext);
  if (!context) {
    throw new Error("useProgress must be used within a ProgressProvider");
  }
  return context;
}

export function ProgressProvider({ children }: { children: React.ReactNode }) {
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [isVisible, setIsVisible] = useState(true);
  const startTimeRef = useRef<number | null>(null);
  const autoProgressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 计算预估剩余时间
  const calculateEstimatedTime = useCallback((currentStep: number, totalSteps: number) => {
    if (!startTimeRef.current || totalSteps <= 1) return null;

    const elapsed = Date.now() - startTimeRef.current;
    const avgTimePerStep = elapsed / currentStep;
    const remainingSteps = totalSteps - currentStep;

    return Math.round(avgTimePerStep * remainingSteps);
  }, []);

  const startProgress = useCallback((id: string, title: string, type: ProgressType, totalSteps: number = 100) => {
    const steps: ProgressStep[] = type === "steps"
      ? Array.from({ length: totalSteps }, (_, i) => ({
          id: `step-${i}`,
          label: `Step ${i + 1}`,
          status: "idle" as ProgressStatus,
        }))
      : [];

    startTimeRef.current = Date.now();

    setProgress({
      id,
      title,
      type,
      status: "running",
      currentStep: 0,
      totalSteps,
      percentage: 0,
      message: "Starting...",
      steps,
      startTime: Date.now(),
      estimatedTimeRemaining: null,
    });

    setIsVisible(true);
  }, []);

  // [NEW] 自动进度更新功能
  const startAutoProgress = useCallback((title: string, totalSteps: number = 10) => {
    console.log("[ProgressContext] Starting auto progress:", title);

    // 清除旧的定时器
    if (autoProgressIntervalRef.current) {
      clearInterval(autoProgressIntervalRef.current);
    }

    const messages = [
      "正在初始化...",
      "正在分析任务需求...",
      "正在准备执行环境...",
      "正在执行主要任务...",
      "正在处理数据...",
      "正在生成结果...",
      "正在优化输出...",
      "正在进行最终检查...",
      "正在准备完成...",
      "即将完成...",
    ];

    let currentPercentage = 0;
    const interval = 500; // 500ms 更新一次
    const incrementPerUpdate = 100 / (totalSteps * 2); // 每次更新的增量

    startTimeRef.current = Date.now();

    setProgress({
      id: "auto-" + Date.now(),
      title,
      type: "percentage",
      status: "running",
      currentStep: 0,
      totalSteps,
      percentage: 0,
      message: messages[0],
      steps: [],
      startTime: Date.now(),
      estimatedTimeRemaining: null,
    });

    setIsVisible(true);

    autoProgressIntervalRef.current = setInterval(() => {
      setProgress((prev) => {
        if (!prev || prev.status !== "running") {
          if (autoProgressIntervalRef.current) {
            clearInterval(autoProgressIntervalRef.current);
            autoProgressIntervalRef.current = null;
          }
          return prev;
        }

        currentPercentage += incrementPerUpdate;
        const newPercentage = Math.min(Math.floor(currentPercentage), 95);
        const messageIndex = Math.min(Math.floor(newPercentage / 10), messages.length - 1);
        const currentStep = Math.floor((newPercentage / 100) * totalSteps);
        const elapsed = Date.now() - (startTimeRef.current || 0);
        const estimatedTime = newPercentage > 0
          ? Math.round((elapsed / newPercentage) * (100 - newPercentage))
          : null;

        console.log("[ProgressContext] Auto progress update:", {
          percentage: newPercentage,
          message: messages[messageIndex],
          currentStep,
        });

        if (newPercentage >= 95) {
          if (autoProgressIntervalRef.current) {
            clearInterval(autoProgressIntervalRef.current);
            autoProgressIntervalRef.current = null;
          }
        }

        return {
          ...prev,
          percentage: newPercentage,
          message: messages[messageIndex],
          currentStep,
          estimatedTimeRemaining: estimatedTime,
        };
      });
    }, interval);
  }, []);

  const updateProgress = useCallback((data: Partial<ProgressState>) => {
    console.log("[ProgressContext] updateProgress called:", data);
    setProgress((prev) => {
      if (!prev) return prev;

      const updated = { ...prev, ...data };

      // 计算预估时间
      if (data.currentStep !== undefined) {
        updated.estimatedTimeRemaining = calculateEstimatedTime(
          data.currentStep,
          prev.totalSteps
        );
      }

      return updated;
    });
  }, [calculateEstimatedTime]);

  const nextStep = useCallback((message?: string) => {
    setProgress((prev) => {
      if (!prev || prev.status !== "running") return prev;

      const nextStepNum = prev.currentStep + 1;
      const percentage = Math.round((nextStepNum / prev.totalSteps) * 100);

      // 更新步骤状态
      const steps = prev.type === "steps" && prev.steps[prev.currentStep]
        ? prev.steps.map((step, idx) =>
            idx === prev.currentStep
              ? { ...step, status: "completed" as ProgressStatus, endTime: Date.now() }
              : idx === nextStepNum && prev.steps[nextStepNum]
              ? { ...prev.steps[nextStepNum], status: "running" as ProgressStatus, startTime: Date.now() }
              : step
          )
        : prev.steps;

      return {
        ...prev,
        currentStep: nextStepNum,
        percentage: Math.min(percentage, 100),
        message: message || `Processing step ${nextStepNum + 1} of ${prev.totalSteps}...`,
        steps,
        estimatedTimeRemaining: calculateEstimatedTime(nextStepNum, prev.totalSteps),
      };
    });
  }, [calculateEstimatedTime]);

  const completeProgress = useCallback((message: string = "Completed!") => {
    console.log("[ProgressContext] completeProgress called");

    // 清除自动进度定时器
    if (autoProgressIntervalRef.current) {
      clearInterval(autoProgressIntervalRef.current);
      autoProgressIntervalRef.current = null;
    }

    setProgress((prev) => {
      if (!prev) return prev;

      const steps = prev.type === "steps"
        ? prev.steps.map((step, idx) =>
            idx <= prev.currentStep
              ? { ...step, status: "completed" as ProgressStatus, endTime: Date.now() }
              : step
          )
        : prev.steps;

      return {
        ...prev,
        status: "completed",
        percentage: 100,
        message,
        steps,
        estimatedTimeRemaining: 0,
      };
    });
  }, []);

  const errorProgress = useCallback((error: string) => {
    console.log("[ProgressContext] errorProgress called:", error);

    // 清除自动进度定时器
    if (autoProgressIntervalRef.current) {
      clearInterval(autoProgressIntervalRef.current);
      autoProgressIntervalRef.current = null;
    }

    setProgress((prev) => {
      if (!prev) return prev;

      const steps = prev.type === "steps"
        ? prev.steps.map((step, idx) =>
            idx <= prev.currentStep
              ? { ...step, status: "error" as ProgressStatus }
              : { ...step, status: "idle" as ProgressStatus }
          )
        : prev.steps;

      return {
        ...prev,
        status: "error",
        message: error,
        steps,
      };
    });
  }, []);

  const resetProgress = useCallback(() => {
    console.log("[ProgressContext] resetProgress called");

    // 清除自动进度定时器
    if (autoProgressIntervalRef.current) {
      clearInterval(autoProgressIntervalRef.current);
      autoProgressIntervalRef.current = null;
    }

    startTimeRef.current = null;
    setProgress(null);
  }, []);

  const show = useCallback(() => setIsVisible(true), []);
  const hide = useCallback(() => setIsVisible(false), []);
  const toggle = useCallback(() => setIsVisible((prev) => !prev), []);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (autoProgressIntervalRef.current) {
        clearInterval(autoProgressIntervalRef.current);
      }
    };
  }, []);

  return (
    <ProgressContext.Provider
      value={{
        progress,
        isVisible,
        startProgress,
        updateProgress,
        nextStep,
        completeProgress,
        errorProgress,
        resetProgress,
        show,
        hide,
        toggle,
        startAutoProgress, // [NEW]
      }}
    >
      {children}
    </ProgressContext.Provider>
  );
}
