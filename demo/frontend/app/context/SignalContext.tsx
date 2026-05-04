"use client";
import { createContext, useContext, useEffect, useRef, useCallback, useState, useMemo } from "react";
import { useAuth } from "./AuthContext";
import { SSEConnection } from "@/app/lib/sse-client";

// 定义 Context 类型以获得更好的类型提示（可选，但推荐）
interface SignalContextType {
  isConnected: boolean;
  projectId: string | null;
  setProjectId: (id: string | null) => void;
  on: (type: string, handler: (data: any) => void) => () => void;
}

const SignalContext = createContext<SignalContextType | null>(null);

const LAST_PROJECT_KEY = "mm_agent_last_project_id";

export const useSignal = () => {
  const context = useContext(SignalContext);
  if (!context) {
    throw new Error("useSignal must be used within a SignalProvider");
  }
  return context;
};

export function SignalProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  
  // [FIX Bug: 项目持久化] 从 localStorage 恢复最后访问的项目
  const [projectId, setProjectId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(LAST_PROJECT_KEY);
    }
    return null;
  });
  
  const [isConnected, setIsConnected] = useState(false);
  const listeners = useRef(new Map());
  const conn = useRef<SSEConnection | null>(null);

  // [FIX Bug: 项目持久化] 当 projectId 变化时，保存到 localStorage
  useEffect(() => {
    if (projectId) {
      localStorage.setItem(LAST_PROJECT_KEY, projectId);
    } else {
      localStorage.removeItem(LAST_PROJECT_KEY);
    }
  }, [projectId]);

  const dispatch = useCallback((data: any, type: string) => {
    listeners.current.get(type)?.forEach((fn: any) => fn(data));
  }, []);

  // SSE 连接逻辑管理
  useEffect(() => {
    conn.current = new SSEConnection(dispatch, (s) => setIsConnected(s === "OPEN"));
    return () => conn.current?.disconnect();
  }, [dispatch]);

  // 根据 projectId 和 token 建立/断开连接
  useEffect(() => {
    if (projectId && token) {
      const root = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
      const cleanRoot = root.includes("/projects") ? root.split("/projects")[0] : root;
      // 注意：后端 SSE 路径通常是 /projects/{id}/events
      conn.current?.connect(`${cleanRoot.replace(/\/$/, "")}/projects/${projectId}/events`, token);
    } else {
      conn.current?.disconnect();
      setIsConnected(false);
    }
  }, [projectId, token]);

  const on = useCallback((type: string, handler: any) => {
    if (!listeners.current.has(type)) listeners.current.set(type, new Set());
    listeners.current.get(type).add(handler);
    return () => listeners.current.get(type)?.delete(handler);
  }, []);

  // [修复核心] 将 projectId 加入 value 对象和依赖数组
  const value = useMemo(() => ({ 
    isConnected, 
    projectId,      // <--- 之前缺失的关键字段
    setProjectId, 
    on 
  }), [isConnected, projectId, setProjectId, on]);

  return <SignalContext.Provider value={value}>{children}</SignalContext.Provider>;
}
