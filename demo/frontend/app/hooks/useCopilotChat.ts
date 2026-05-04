"use client";
import { useRef, useCallback } from "react";
import { useCopilot } from "@/app/context/CopilotContext";
import { useSecureConfig } from "@/app/hooks/useSecureConfig";
import { useUI } from "@/app/hooks/useUI";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useAuth } from "@/app/context/AuthContext";
import { useSignal } from "@/app/context/SignalContext";
import { useStageStore } from "@/lib/stores";

export function useCopilotChat() {
  const { messages, addMessage, updateMessage, setStreaming, currentSessionId, createNewSession } = useCopilot();
  const { projectId } = useSignal();
  const { selectedNodeId } = useStageStore();
  const { config, getLLMHeaders } = useSecureConfig();
  const { token } = useAuth();
  const { toast } = useUI();
  const abortCtrl = useRef<AbortController | null>(null);

  // [FIX] Use a Ref to buffer stream content across renders
  const streamBuffer = useRef<{ content: string; thought: string }>({ content: "", thought: "" });

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || !projectId) return;
    
    // 1. Ensure Session Exists
    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
        try {
            activeSessionId = await createNewSession();
        } catch (e) {
            toast.error("Failed to start new session");
            return;
        }
    }

    // 2. Optimistic UI Update
    addMessage({ role: "user", content });
    const botMsgId = addMessage({ role: "assistant", content: "", isStreaming: true });
    setStreaming(true);
    
    abortCtrl.current = new AbortController();
    streamBuffer.current = { content: "", thought: "" }; // Reset buffer

    try {
      const root = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
      const cleanRoot = root.includes("/projects") ? root.split("/projects")[0] : root;

      await fetchEventSource(`${cleanRoot.replace(/\/$/, "")}/copilot/chat`, {
        method: "POST", 
        headers: { 
            "Content-Type": "application/json", 
            "Authorization": `Bearer ${token}`,
            ...getLLMHeaders() // [BYOK] Inject user configuration headers
        },
        body: JSON.stringify({ 
            project_id: projectId, 
            current_node_id: selectedNodeId || null, 
            session_id: activeSessionId, // [NEW] Pass the guaranteed session ID
            messages: [{ role: "user", content }], // Only send current message, backend handles history
            model_config: config 
        }),
        signal: abortCtrl.current.signal,
        async onopen(res) {
            if (res.ok && res.headers.get("content-type")?.includes("text/event-stream")) {
                return;
            }
            if (res.status === 401 || res.status === 403) {
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new Event("auth:unauthorized"));
                }
                throw new Error("Unauthorized");
            }
            if (res.status >= 400 && res.status < 500) {
                const txt = await res.text();
                throw new Error(`Client Error: ${txt}`);
            }
        },
        onmessage(msg) {
          if (msg.event === "token") {
            try {
              const data = JSON.parse(msg.data);
              
              // [FIX] Append to Ref buffer
              if (data.content) streamBuffer.current.content += data.content;
              if (data.thought) streamBuffer.current.thought += data.thought;
              
              // [FIX] Update State with full buffer content
              updateMessage(botMsgId, { 
                content: streamBuffer.current.content, 
                thought: streamBuffer.current.thought 
              });
            } catch {}
          }
        },
        onclose() {
            // Stream ended normally; returning stops retries.
        },
        onerror(err) {
            if (err.message === "Unauthorized" || err.message.startsWith("Client Error")) {
                throw err;
            }
            throw err;
        }
      });
    } catch (err: any) {
      if (!abortCtrl.current?.signal.aborted) { 
          const msg = err.message || "Connection failed";
          toast.error(`Copilot Error: ${msg}`); 
          updateMessage(botMsgId, { content: streamBuffer.current.content + `\n\n**[Error]**: ${msg}` }); 
      }
    } finally {
      setStreaming(false); 
      updateMessage(botMsgId, { isStreaming: false }); 
      abortCtrl.current = null;
    }
  }, [projectId, selectedNodeId, config, getLLMHeaders, token, addMessage, updateMessage, setStreaming, currentSessionId, createNewSession, toast]);

  const abortGeneration = useCallback(() => {
    if (abortCtrl.current) { abortCtrl.current.abort(); abortCtrl.current = null; setStreaming(false); toast.info("Stopped"); }
  }, [setStreaming, toast]);

  return { sendMessage, abortGeneration };
}
