"use client";
import { cn } from "@/lib/utils";
import { Home, ChevronRight, Settings, Menu, PanelLeft, Zap, Download, Loader2 } from "lucide-react";
import { useStatusVariant } from "@/app/hooks/useStatusVariant";
import { useSignal } from "@/app/context/SignalContext";
import { useStageStore } from "@/lib/stores";
import { useProjectExport } from "@/app/hooks/useProjectExport";

export function UnifiedHeader({ projectId, projectName, workspace, isSidebarOpen, onToggleSidebar, onBack, onSettings }: any) {
  const { isConnected } = useSignal();
  const { isAgentWorking } = useStageStore();
  const status = useStatusVariant({
    status: workspace?.state?.status,
    statusOverride: isAgentWorking ? "RUNNING" : undefined
  });

  // Export Hook Integration
  const { triggerExport, isExporting } = useProjectExport();

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-4 shrink-0 z-20">
      <div className="flex items-center gap-4 min-w-0 flex-1">
        <button onClick={onToggleSidebar} className="p-2 -ml-2 hover:bg-slate-100 rounded-lg text-slate-500">{isSidebarOpen ? <PanelLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}</button>
        <div className="h-5 w-px bg-slate-200" />
        <nav className="flex items-center gap-2 text-sm min-w-0">
          <button onClick={onBack}><Home className="w-4 h-4 text-slate-400 hover:text-slate-700" /></button>
          <ChevronRight className="w-4 h-4 text-slate-300 shrink-0" />
          <span className="font-medium text-slate-600 truncate max-w-[150px]">{projectName}</span>
          {workspace && <><ChevronRight className="w-4 h-4 text-slate-300 shrink-0" /><span className="font-bold text-slate-900 bg-slate-50 px-2 py-1 rounded border border-slate-100">{workspace.definition.type.replace(/_/g, " ")}</span></>}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        {workspace && <div className="text-xs font-medium text-slate-500 px-2 py-1">
          {status.label}
        </div>}
        <div className="px-2" title={isConnected ? "Connected" : "Disconnected"}><Zap className={cn("w-3.5 h-3.5", isConnected ? "text-emerald-500 fill-emerald-500" : "text-slate-300")} /></div>
        
        {/* Export Action */}
        {workspace && projectId && (
          <button 
            onClick={() => triggerExport(projectId)} 
            disabled={isExporting}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors disabled:opacity-50"
            title="Export Project Archive"
          >
            {isExporting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Download className="w-5 h-5" />}
          </button>
        )}

        <button onClick={onSettings} className="p-2 text-slate-400 hover:bg-slate-100 rounded"><Settings className="w-5 h-5" /></button>
      </div>
    </header>
  );
}
