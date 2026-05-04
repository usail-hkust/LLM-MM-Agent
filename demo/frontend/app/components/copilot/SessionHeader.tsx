"use client";
import { useState } from "react";
import { Plus, ChevronDown, Trash2, MessageSquare, Eraser, ChevronRight } from "lucide-react";
import { useCopilot } from "@/app/context/CopilotContext";
import { useCopilotUIStore } from "@/lib/stores/copilot-ui";
import { cn } from "@/lib/utils";

export function SessionHeader() {
  const { sessions, currentSessionId, switchSession, createNewSession, deleteSession, clearMessages } = useCopilot();
  const togglePanel = useCopilotUIStore((s) => s.toggle);
  const [open, setOpen] = useState(false);

  const currentSession = sessions.find(s => s.id === currentSessionId);

  return (
    <div className="h-[var(--header-height)] border-b border-slate-200 bg-white flex items-center justify-between px-3 shrink-0 relative z-30">
      
      {/* Session Switcher */}
      <div className="relative">
        <button 
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 hover:bg-slate-100 px-2 py-1.5 rounded-lg transition-colors max-w-[200px] outline-none"
        >
          <span className="text-sm font-semibold text-slate-700 truncate">
            {currentSession?.title || "New Chat"}
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
        </button>
        
        {open && (
          <>
            <div 
              className="fixed inset-0 z-40" 
              onClick={() => setOpen(false)}
            />
            <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-slate-200 rounded-lg shadow-lg z-50 p-2">
              <button 
                onClick={() => { createNewSession(); setOpen(false); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 rounded-md mb-2 border border-dashed border-slate-200 transition-colors"
              >
                <Plus className="w-4 h-4" /> New Chat
              </button>
              
              <div className="max-h-[300px] overflow-y-auto custom-scrollbar space-y-1">
                {sessions.map(session => (
                  <div 
                    key={session.id} 
                    className={cn(
                      "group flex items-center justify-between px-3 py-2 rounded-md cursor-pointer text-sm transition-colors",
                      session.id === currentSessionId ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"
                    )}
                    onClick={() => { switchSession(session.id); setOpen(false); }}
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                        <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-70"/>
                        <span className="truncate">{session.title}</span>
                    </div>
                    <button 
                        onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-opacity"
                        title="Delete session"
                    >
                        <Trash2 className="w-3 h-3"/>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-1">
        <button onClick={clearMessages} className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors" title="Clear View">
          <Eraser className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-slate-200 mx-1" />
        <button onClick={togglePanel} className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors" title="Close Panel">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
