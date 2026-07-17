"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Modal } from "@/components/ui/modal";
import { ConvexSurface } from "@/components/convex-surface";
import { AnalysisResult } from "@/lib/types";
import { useAssistantChat } from "@/hooks/useAssistantChat";
import { ChatBubble } from "@/components/chat/ChatBubble";

interface AssistantChatProps {
  open: boolean;
  result: AnalysisResult | null;
  onClose: () => void;
}

export function AssistantChat({ open, result, onClose }: AssistantChatProps) {
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
    <Modal
      open={open}
      onClose={onClose}
      labelledBy="assistant-title"
      className="overlay overlay--chat"
    >
      <ConvexSurface variant="panel" className="chat">
        <header className="chat__head">
          <div>
            <p className="section-tag">Asisten simulasi</p>
            <h2 id="assistant-title" className="chat__title">
              Analisis dengan AI
            </h2>
          </div>
          <button
            type="button"
            className="chat__close"
            onClick={onClose}
            aria-label="Tutup obrolan"
          >
            Tutup
          </button>
        </header>

        <div className="chat__messages" ref={listRef} aria-live="polite">
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

        <div className="chat__quick">
          {quickReplies.map((reply) => (
            <button
              type="button"
              key={reply}
              className="chat__chip"
              onClick={() => void send(reply)}
              disabled={pending}
            >
              {reply}
            </button>
          ))}
        </div>

        <form className="chat__form" onSubmit={submit}>
          <input
            className="chat__input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Tulis pertanyaan…"
            aria-label="Tulis pertanyaan"
          />
          <button type="submit" className="btn-primary" disabled={pending || !draft.trim()}>
            Kirim
          </button>
        </form>

        <p className="chat__disclaimer">
          Jawaban bersifat umum dan simulasi — bukan diagnosis medis.
        </p>
      </ConvexSurface>
    </Modal>
  );
}
