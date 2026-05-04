"use client";

import { ReactNode, useEffect, useState } from "react";
import { useConfigStore } from "@/lib/stores";
import { AlertCircle, RefreshCw, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * [Resilience] Config Gate with Timeout Fallback
 * Prevents indefinite white screen if Zustand persistence hydration fails.
 * Provides a UI to recover or reset settings manually.
 */
export function ConfigHydrationGate({ children }: { children: ReactNode }) {
  const { hasHydrated, setIsOpen } = useConfigStore();
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    useConfigStore.persist.rehydrate();
  }, []);

  useEffect(() => {
    if (hasHydrated) return;

    const timer = setTimeout(() => {
      setShowFallback(true);
    }, 1500);

    return () => clearTimeout(timer);
  }, [hasHydrated]);

  if (hasHydrated) {
    return <>{children}</>;
  }

  if (!showFallback) {
    return null;
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 p-6 animate-in fade-in duration-500">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-100 p-8 text-center space-y-6">
        <div className="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-slate-900">Configuration Sync Failed</h2>
          <p className="text-slate-500 text-sm leading-relaxed">
            The application is taking too long to load your settings. This may be due to browser storage restrictions.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <Button 
            variant="outline" 
            onClick={() => window.location.reload()}
            className="w-full gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reload
          </Button>
          <Button 
            onClick={() => setIsOpen(true)}
            className="w-full gap-2 bg-slate-900 hover:bg-slate-800 text-white"
          >
            <Settings2 className="w-4 h-4" />
            Open Settings
          </Button>
        </div>

        <div className="pt-4 border-t border-slate-100">
          <p className="text-xs text-slate-400">
            If you see this often, check if Local Storage is enabled in your browser.
          </p>
        </div>
      </div>
    </div>
  );
}
