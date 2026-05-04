"use client";

import React, { useEffect } from "react";
import { ProgressProvider, useProgress } from "@/app/context/ProgressContext";
import { ProgressIndicator } from "@/app/components/ui/ProgressIndicator";
import { Button } from "@/components/ui/button";

function TestComponent() {
  const { 
    progress, 
    startProgress, 
    updateProgress, 
    nextStep, 
    completeProgress, 
    errorProgress, 
    resetProgress 
  } = useProgress();

  const testLinear = () => {
    startProgress("test-linear", "Processing Data", "linear", 100);
    
    // 模拟进度更新
    let current = 0;
    const interval = setInterval(() => {
      current += Math.random() * 10;
      if (current >= 100) {
        clearInterval(interval);
        completeProgress("Data processed successfully!");
      } else {
        updateProgress({ 
          percentage: Math.round(current),
          message: `Processing... ${Math.round(current)}%`
        });
      }
    }, 200);
  };

  const testSteps = () => {
    startProgress("test-steps", "Running Agent Pipeline", "steps", 5);
    nextStep("Initializing...");
    
    // 模拟步骤执行
    const runSteps = async () => {
      await new Promise(r => setTimeout(r, 500));
      nextStep("Analyzing input...");
      await new Promise(r => setTimeout(r, 800));
      nextStep("Generating response...");
      await new Promise(r => setTimeout(r, 600));
      nextStep("Formatting output...");
      await new Promise(r => setTimeout(r, 400));
      completeProgress("Pipeline completed!");
    };
    
    runSteps();
  };

  const testPercentage = () => {
    startProgress("test-pct", "Training Model", "percentage", 100);
    
    let current = 0;
    const interval = setInterval(() => {
      current += Math.random() * 5;
      if (current >= 100) {
        clearInterval(interval);
        completeProgress("Training complete!");
      } else {
        updateProgress({ 
          percentage: Math.round(current),
          message: `Epoch ${Math.round(current / 10)}/10`
        });
      }
    }, 300);
  };

  const testError = () => {
    startProgress("test-error", "Processing", "linear", 100);
    
    setTimeout(() => {
      errorProgress("Failed to connect to server");
    }, 1500);
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Progress Component Test</h1>
      
      <div className="space-y-4 mb-8">
        <div className="p-4 border rounded-lg">
          <h2 className="font-semibold mb-2">Current Progress</h2>
          {progress ? (
            <div>
              <p><strong>ID:</strong> {progress.id}</p>
              <p><strong>Title:</strong> {progress.title}</p>
              <p><strong>Status:</strong> {progress.status}</p>
              <p><strong>Message:</strong> {progress.message}</p>
              <p><strong>Progress:</strong> {progress.percentage}%</p>
              {progress.estimatedTimeRemaining !== null && (
                <p><strong>ETA:</strong> {progress.estimatedTimeRemaining}ms</p>
              )}
            </div>
          ) : (
            <p className="text-slate-500">No active progress</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-4">
        <Button onClick={testLinear}>Test Linear Progress</Button>
        <Button onClick={testSteps}>Test Steps Progress</Button>
        <Button onClick={testPercentage}>Test Percentage Progress</Button>
        <Button onClick={testError} variant="destructive">Test Error State</Button>
        <Button onClick={resetProgress} variant="outline">Reset</Button>
      </div>
    </div>
  );
}

export default function TestPage() {
  return (
    <ProgressProvider>
      <TestComponent />
      <ProgressIndicator />
    </ProgressProvider>
  );
}
