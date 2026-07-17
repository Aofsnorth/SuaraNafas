"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ConvexSurface } from "@/components/convex-surface";
import { AnalysisResult } from "@/lib/types";
import { useAssistantChat } from "@/hooks/useAssistantChat";
import { ChatBubble } from "@/components/chat/ChatBubble";

interface AssistantChatProps {
  result: AnalysisResult | null;
  onClose: () => void;
}

export function AssistantChat({ result, onClose }: AssistantChatProps) {
  const { messages, quickReplies, pending, send } = useAssistantChat(result);
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = listRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, pending]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft;
    setDraft("");
    void send(text);
  };

  return (
    <ConvexSurface
      variant="panel"
      className="chat w-full flex flex-col justify-between p-6 md:p-8 min-h-[450px]"
      aria-labelledby="assistant-title"
    >
      <header className="chat__head flex items-center justify-between pb-4 border-b border-rule">
        <div>
          <p className="section-tag">Asisten simulasi</p>
          <h2 id="assistant-title" className="text-xl font-heading">
            Analisis dengan AI
          </h2>
        </div>
        <button
          type="button"
          className="text-xs text-muted hover:text-ink cursor-pointer"
          onClick={onClose}
          aria-label="Tutup obrolan"
        >
          Kembali
        </button>
      </header>

      <div className="chat__messages flex-1 overflow-y-auto my-4 max-h-[300px] pr-2 space-y-3" ref={listRef} aria-live="polite">
        {messages.map((message) => (
          <ChatBubble key={message.id} message={message} />
        ))}
        {pending ? (
          <div className="chat-bubble chat-bubble--assistant chat-bubble--typing">
            <span />
            <span />
            <span />
          </div>
        ) : null}
      </div>

      <div className="pt-4 border-t border-rule space-y-4">
        <div className="chat__quick flex flex-wrap gap-2">
          {quickReplies.map((reply) => (
            <button
              type="button"
              key={reply}
              className="chat__chip text-xs px-3 py-1 bg-white/[0.04] border border-white/[0.08] rounded-full hover:bg-white/[0.08] transition-colors"
              onClick={() => void send(reply)}
              disabled={pending}
            >
              {reply}
            </button>
          ))}
        </div>

        <form className="chat__form flex gap-2" onSubmit={submit}>
          <input
            className="chat__input flex-1 px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-md text-sm text-ink focus:outline-none focus:border-accent"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Tulis pertanyaan…"
            aria-label="Tulis pertanyaan"
          />
          <button type="submit" className="btn-primary py-2 px-4" disabled={pending || !draft.trim()}>
            Kirim
          </button>
        </form>

        <p className="chat__disclaimer text-[10px] text-muted text-center">
          Jawaban bersifat umum dan simulasi — bukan diagnosis medis.
        </p>
      </div>
    </ConvexSurface>
  );
}
