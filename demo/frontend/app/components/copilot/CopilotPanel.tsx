"use client";

import { useCopilot } from "@/app/context/CopilotContext";
import { useCopilotChat } from "@/app/hooks/useCopilotChat";
import { SessionHeader } from "./SessionHeader";
import { MessageList } from "./MessageList";
import { CopilotInput } from "./CopilotInput";

export function CopilotPanel() {
  const { isStreaming } = useCopilot();
  const { sendMessage, abortGeneration } = useCopilotChat();

  return (
    <div className="h-full w-full bg-slate-50/50 flex flex-col min-h-0 min-w-[300px]">
      <SessionHeader />
      <MessageList />
      <CopilotInput onSend={sendMessage} isStreaming={isStreaming} onStop={abortGeneration} />
    </div>
  );
}
