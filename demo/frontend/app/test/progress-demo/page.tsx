"use client";

import { useState } from "react";
import { useProgress } from "@/app/context/ProgressContext";
import { AgentProgressPanel } from "@/app/components/stage/AgentProgressPanel";
import { useStageStore } from "@/lib/stores";

export default function ProgressDemoPage() {
  const { startProgress, updateProgress, completeProgress, progress } = useProgress();
  const { setAgentWorking, setNodeStatus, setNodeType } = useStageStore();
  const [isSimulating, setIsSimulating] = useState(false);

  const startSimulation = () => {
    setAgentWorking(true);
    setNodeStatus("DRAFTING");
    setNodeType("CODE_GENERATOR");
    setIsSimulating(true);

    // 启动进度追踪
    startProgress("test-node", "Code Generation Test", "percentage", 10);

    // 模拟进度更新
    let percentage = 0;
    const messages = [
      "正在分析需求...",
      "正在生成代码框架...",
      "正在编写实现代码...",
      "正在优化代码逻辑...",
      "正在添加注释和文档...",
      "正在进行最终检查...",
    ];

    const interval = setInterval(() => {
      percentage += 10;
      const messageIndex = Math.min(Math.floor(percentage / 20), messages.length - 1);

      updateProgress({
        percentage,
        message: messages[messageIndex],
        currentStep: Math.floor(percentage / 10),
        estimatedTimeRemaining: (100 - percentage) * 1000,
      });

      if (percentage >= 90) {
        clearInterval(interval);
        setTimeout(() => {
          completeProgress("代码生成完成！");
          setAgentWorking(false);
          setIsSimulating(false);
        }, 1000);
      }
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">进度系统测试页面</h1>

        <div className="bg-white rounded-xl p-6 shadow-sm mb-6">
          <h2 className="text-xl font-semibold mb-4">控制面板</h2>

          <div className="space-y-4">
            <button
              onClick={startSimulation}
              disabled={isSimulating}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSimulating ? "模拟进行中..." : "开始模拟进度"}
            </button>

            <div className="bg-slate-50 rounded-lg p-4">
              <h3 className="font-semibold mb-2">当前状态：</h3>
              <pre className="text-sm text-slate-600 overflow-auto">
                {JSON.stringify(
                  {
                    isSimulating,
                    progress: progress
                      ? {
                          id: progress.id,
                          title: progress.title,
                          percentage: progress.percentage,
                          message: progress.message,
                          currentStep: progress.currentStep,
                          totalSteps: progress.totalSteps,
                          status: progress.status,
                        }
                      : null,
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          </div>
        </div>

        {/* 显示 AgentProgressPanel */}
        <div className="relative h-32 border-2 border-dashed border-slate-300 rounded-lg flex items-center justify-center">
          <span className="text-slate-400">AgentProgressPanel 应该显示在这里 ↑</span>
        </div>

        {/* 实际的进度面板 */}
        <AgentProgressPanel />
      </div>
    </div>
  );
}
