"use client";

import { useState } from "react";
import { Key, Globe, Cpu, Save, Box, CheckCircle, XCircle, Loader2, RefreshCw } from "lucide-react";
import { useConfigStore } from "@/lib/stores";
import { useSecureConfig } from "@/app/hooks/useSecureConfig";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ValidationResult {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}

export function SettingsModal() {
  const { isOpen, setIsOpen } = useConfigStore();
  const { config, updateConfig } = useSecureConfig();
  
  const [isValidating, setIsValidating] = useState<"llm" | "e2b" | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  const validateConfig = async (provider: "llm" | "e2b") => {
    setIsValidating(provider);
    setValidationResult(null);

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
      
      const response = await fetch(`${API_BASE}/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider,
          apiKey: provider === "llm" ? config.apiKey : config.e2bKey,
          baseUrl: config.baseUrl,
          modelName: config.modelName,
        }),
      });

      const data = await response.json();
      setValidationResult(data);
    } catch (error) {
      setValidationResult({
        success: false,
        message: `Connection error: ${error instanceof Error ? error.message : "Unknown error"}`,
      });
    } finally {
      setIsValidating(null);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Execution Settings</DialogTitle>
          <DialogDescription>
            Configure the LLM provider for the agentic backend.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Validation Result Alert */}
          {validationResult && (
            <div className={`p-4 rounded-xl border ${
              validationResult.success 
                ? "bg-green-50 border-green-200 text-green-800" 
                : "bg-red-50 border-red-200 text-red-800"
            }`}>
              <div className="flex items-center gap-2">
                {validationResult.success ? (
                  <CheckCircle className="w-5 h-5" />
                ) : (
                  <XCircle className="w-5 h-5" />
                )}
                <span className="font-medium">{validationResult.message}</span>
              </div>
            </div>
          )}

          <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4 text-xs text-blue-800 leading-relaxed">
            <strong>Note:</strong> These settings are stored locally. 
            API Keys are stored in <strong>Local Storage</strong> and will persist across browser sessions.
            They are sent to the backend as <code className="bg-blue-100 px-1 py-0.5 rounded">X-LLM-*</code> headers.
          </div>

          {/* Model Name */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-2">
              <div className="p-1 bg-slate-100 rounded-md">
                <Cpu className="w-3.5 h-3.5" />
              </div>
              Model Name
            </label>
            <input
              type="text"
              placeholder="e.g., claude-3-5-sonnet-20241022"
              value={config.modelName}
              onChange={(e) => {
                updateConfig({ modelName: e.target.value });
                setValidationResult(null);
              }}
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-slate-400 font-mono transition-all"
            />
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-2">
                <div className="p-1 bg-slate-100 rounded-md">
                  <Key className="w-3.5 h-3.5" />
                </div>
                API Key
              </label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => validateConfig("llm")}
                disabled={!config.apiKey || isValidating === "llm"}
                className="h-7 text-xs gap-1"
              >
                {isValidating === "llm" ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3 h-3" />
                    Test Connection
                  </>
                )}
              </Button>
            </div>
            <div className="relative">
              <input
                type="password"
                placeholder="sk-ant-api03-..."
                value={config.apiKey}
                onChange={(e) => {
                  updateConfig({ apiKey: e.target.value });
                  setValidationResult(null);
                }}
                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-slate-400 font-mono transition-all pr-12"
              />
              <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none">
                {config.apiKey ? (
                  <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-bold">SET</span>
                ) : (
                  <span className="text-[10px] bg-slate-100 text-slate-400 px-2 py-0.5 rounded-full font-bold">EMPTY</span>
                )}
              </div>
            </div>
          </div>

          {/* E2B API Key */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-2">
                <div className="p-1 bg-slate-100 rounded-md">
                  <Box className="w-3.5 h-3.5" />
                </div>
                E2B API Key
              </label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => validateConfig("e2b")}
                disabled={!config.e2bKey || isValidating === "e2b"}
                className="h-7 text-xs gap-1"
              >
                {isValidating === "e2b" ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Testing...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3 h-3" />
                    Test Connection
                  </>
                )}
              </Button>
            </div>
            <div className="relative">
              <input
                type="password"
                placeholder="e2b_..."
                value={config.e2bKey || ""}
                onChange={(e) => {
                  updateConfig({ e2bKey: e.target.value });
                  setValidationResult(null);
                }}
                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-slate-400 font-mono transition-all pr-12"
              />
              <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none">
                {config.e2bKey ? (
                  <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-bold">SET</span>
                ) : (
                  <span className="text-[10px] bg-slate-100 text-slate-400 px-2 py-0.5 rounded-full font-bold">EMPTY</span>
                )}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 px-1">Required for code execution sandbox.</p>
          </div>

          {/* Base URL */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wide flex items-center gap-2">
              <div className="p-1 bg-slate-100 rounded-md">
                <Globe className="w-3.5 h-3.5" />
              </div>
              Base URL (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g., https://api.openrouter.ai/v1"
              value={config.baseUrl}
              onChange={(e) => {
                updateConfig({ baseUrl: e.target.value });
                setValidationResult(null);
              }}
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/5 focus:border-slate-400 font-mono text-slate-600 transition-all"
            />
            <p className="text-[11px] text-slate-400 px-1">
              Use this if you are using a proxy or a compatible provider like OpenRouter, SiliconFlow, etc.
            </p>
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" className="gap-2">
              <Save className="w-4 h-4" /> Save & Close
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
