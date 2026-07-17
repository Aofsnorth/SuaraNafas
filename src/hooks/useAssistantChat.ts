"use client";

import { useCallback, useMemo, useState } from "react";
import { ChatMessage } from "@/models/chat";
import { AnalysisResult } from "@/lib/types";
import { createAssistantProvider } from "@/services/assistant-service";

let messageCounter = 0;
function nextId() {
  messageCounter += 1;
  return `msg-${messageCounter}`;
}

interface UseAssistantChatReturn {
  messages: ChatMessage[];
  quickReplies: string[];
  pending: boolean;
  send: (text: string) => Promise<void>;
}

export function useAssistantChat(result: AnalysisResult | null): UseAssistantChatReturn {
  const provider = useMemo(() => createAssistantProvider(), []);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    { id: nextId(), role: "assistant", content: provider.greeting(result) },
  ]);
  const [pending, setPending] = useState(false);

  const send = useCallback(
    async (text: string) => {
      const content = text.trim();
      if (!content || pending) return;

      setMessages((prev) => [...prev, { id: nextId(), role: "user", content }]);
      setPending(true);
      const answer = await provider.reply(content, result);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", content: answer },
      ]);
      setPending(false);
    },
    [pending, provider, result],
  );

  return { messages, quickReplies: provider.quickReplies(), pending, send };
}
