"use client";

import React from "react";
import { useProgress, ProgressState } from "@/app/context/ProgressContext";
import { motion, AnimatePresence } from "framer-motion";
import { X, Clock, CheckCircle, AlertCircle, Loader2 } from "lucide-react";

export function ProgressIndicator() {
  const { progress, isVisible, hide, resetProgress } = useProgress();

  // 不显示空状态
  if (!progress || !isVisible) return null;

  const handleClose = () => {
    hide();
    setTimeout(resetProgress, 500); // 延迟重置让动画完成
  };

  const formatTime = (ms: number | null) => {
    if (ms === null || ms === undefined) return "--";
    if (ms < 1000) return "< 1s";
    if (ms < 60000) return `${Math.round(ms / 1000)}s`;
    return `${Math.round(ms / 60000)}m`;
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -20, scale: 0.95 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        className="fixed top-4 right-4 z-50 w-80 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-100">
          <div className="flex items-center gap-2">
            {progress.status === "running" && (
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            )}
            {progress.status === "completed" && (
              <CheckCircle className="w-4 h-4 text-green-500" />
            )}
            {progress.status === "error" && (
              <AlertCircle className="w-4 h-4 text-red-500" />
            )}
            <span className="font-semibold text-sm text-slate-700">
              {progress.title}
            </span>
          </div>
          <button
            onClick={handleClose}
            className="p-1 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {/* Message */}
          <p className="text-sm text-slate-600 mb-3">{progress.message}</p>

          {/* Progress Bar */}
          {progress.type === "linear" && (
            <div className="relative h-2 bg-slate-100 rounded-full overflow-hidden">
              <motion.div
                className={`absolute left-0 top-0 h-full rounded-full ${
                  progress.status === "error" ? "bg-red-500" : "bg-blue-500"
                }`}
                initial={{ width: 0 }}
                animate={{ width: `${progress.percentage}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          )}

          {progress.type === "percentage" && (
            <div className="flex items-center justify-center mb-3">
              <div className="relative w-16 h-16">
                <svg className="w-16 h-16 transform -rotate-90">
                  <circle
                    cx="32"
                    cy="32"
                    r="28"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="transparent"
                    className="text-slate-100"
                  />
                  <motion.circle
                    cx="32"
                    cy="32"
                    r="28"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="transparent"
                    className={`${
                      progress.status === "error" ? "text-red-500" : "text-blue-500"
                    }`}
                    strokeDasharray={175.93}
                    strokeDashoffset={175.93 - (175.93 * progress.percentage) / 100}
                    initial={{ strokeDashoffset: 175.93 }}
                    animate={{ strokeDashoffset: 175.93 - (175.93 * progress.percentage) / 100 }}
                    transition={{ duration: 0.3 }}
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-slate-700">
                  {progress.percentage}%
                </span>
              </div>
            </div>
          )}

          {/* Steps */}
          {progress.type === "steps" && (
            <div className="space-y-2 mb-3 max-h-32 overflow-y-auto">
              {progress.steps.slice(0, 5).map((step, idx) => (
                <div
                  key={step.id}
                  className={`flex items-center gap-2 text-xs ${
                    idx <= progress.currentStep ? "text-slate-700" : "text-slate-400"
                  }`}
                >
                  {idx < progress.currentStep && (
                    <CheckCircle className="w-3 h-3 text-green-500" />
                  )}
                  {idx === progress.currentStep && progress.status === "running" && (
                    <Loader2 className="w-3 h-3 animate-spin text-blue-500" />
                  )}
                  {idx > progress.currentStep && (
                    <div className="w-3 h-3 border-2 border-slate-300 rounded-full" />
                  )}
                  <span className={idx <= progress.currentStep ? "font-medium" : ""}>
                    {step.label}
                  </span>
                </div>
              ))}
              {progress.steps.length > 5 && (
                <p className="text-xs text-slate-400">
                  +{progress.steps.length - 5} more steps...
                </p>
              )}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
            {progress.status === "running" && progress.estimatedTimeRemaining !== null && (
              <div className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                <span>~{formatTime(progress.estimatedTimeRemaining)} remaining</span>
              </div>
            )}
            {progress.type !== "steps" && (
              <div className="ml-auto">
                {progress.currentStep}/{progress.totalSteps}
              </div>
            )}
            {progress.type === "steps" && (
              <div className="ml-auto">
                Step {progress.currentStep + 1} of {progress.totalSteps}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

// 简化的内联进度条组件
export function InlineProgress({ 
  progress, 
  className = "" 
}: { 
  progress: ProgressState | null; 
  className?: string;
}) {
  if (!progress) return null;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            progress.status === "error" ? "bg-red-500" : "bg-blue-500"
          }`}
          style={{ width: `${progress.percentage}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 w-10 text-right">
        {progress.percentage}%
      </span>
    </div>
  );
}
