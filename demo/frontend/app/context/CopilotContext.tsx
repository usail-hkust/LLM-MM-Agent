"use client";
import React, { createContext, useContext, useState, useMemo, useEffect, useCallback } from "react";
import { nanoid } from "@/lib/utils";
import { useSignal } from "@/app/context/SignalContext";
import { apiClient } from "@/app/lib/api-client";
import { useAuth } from "@/app/context/AuthContext";

export interface CopilotMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  thought?: string;
  isStreaming?: boolean;
  timestamp: number;
}

export interface CopilotSession {
  id: string;
  title: string;
  updated_at: string;
}

interface CopilotContextType {
  // Session State
  sessions: CopilotSession[];
  currentSessionId: string | null;
  createNewSession: () => Promise<string>; // Return ID for immediate use
  switchSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  
  // Chat State
  messages: CopilotMessage[];
  isStreaming: boolean;
  addMessage: (msg: Omit<CopilotMessage, "id" | "timestamp">) => string;
  updateMessage: (id: string, updates: Partial<CopilotMessage>) => void;
  clearMessages: () => void; // Clears view, effectively "New Chat" state visually
  setStreaming: (streaming: boolean) => void;
}

const CopilotContext = createContext<CopilotContextType | null>(null);
export const useCopilot = () => useContext(CopilotContext)!;

export function CopilotProvider({ children }: { children: React.ReactNode }) {
  const { projectId } = useSignal();
  const { token } = useAuth();
  
  const [sessions, setSessions] = useState<CopilotSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Load Sessions when Project changes
  useEffect(() => {
    if (projectId && token) {
      apiClient<CopilotSession[]>(`/projects/${projectId}/sessions`, token)
        .then(data => {
          setSessions(data);
          // Optional: Auto-load last session or stay on New Chat
          // Keeping it null means "New Chat" ready state
        })
        .catch(console.error);
    } else {
        setSessions([]);
        setMessages([]);
        setCurrentSessionId(null);
    }
  }, [projectId, token]);

  const createNewSession = useCallback(async () => {
    if (!projectId || !token) throw new Error("No project context");
    
    // Optimistic UI handled by caller usually, but here we create on server first
    const newSession = await apiClient<CopilotSession>(`/projects/${projectId}/sessions`, token, { method: "POST" });
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
    setMessages([]); // Clear chat for new session
    return newSession.id;
  }, [projectId, token]);

  const switchSession = useCallback(async (id: string) => {
    if (!token) return;
    setCurrentSessionId(id);
    setMessages([]); // Clear while loading
    try {
      const history = await apiClient<any[]>(`/sessions/${id}/messages`, token);
      setMessages(history.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        thought: m.thought,
        timestamp: m.timestamp
      })));
    } catch (e) {
      console.error("Failed to load session", e);
    }
  }, [token]);

  const deleteSession = useCallback(async (id: string) => {
      if(!token) return;
      try {
          await apiClient(`/sessions/${id}`, token, { method: "DELETE" });
          setSessions(prev => prev.filter(s => s.id !== id));
          if (currentSessionId === id) {
              setCurrentSessionId(null);
              setMessages([]);
          }
      } catch (e) { console.error(e); }
  }, [token, currentSessionId]);

  // Chat Helpers
  const addMessage = useCallback((msg: Omit<CopilotMessage, "id" | "timestamp">) => {
    const id = nanoid();
    setMessages(prev => [...prev, { ...msg, id, timestamp: Date.now() }]);
    return id;
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<CopilotMessage>) => {
    setMessages(prev => prev.map(m => (m.id === id ? { ...m, ...updates } : m)));
  }, []);

  const clearMessages = useCallback(() => {
      setMessages([]);
      setCurrentSessionId(null); // Reset to "New Chat" mode
  }, []);

  const value = useMemo(() => ({
    sessions, currentSessionId, messages, isStreaming,
    createNewSession, switchSession, deleteSession,
    addMessage, updateMessage, clearMessages, setStreaming: setIsStreaming
  }), [sessions, currentSessionId, messages, isStreaming, createNewSession, switchSession, deleteSession, addMessage, updateMessage, clearMessages]);

  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}
