"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
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
    <section className="panel chat" aria-labelledby="assistant-title">
      <header className="chat__head">
        <div>
          <p className="eyebrow chat__eyebrow">Asisten AI</p>
          <h2 id="assistant-title">Tanya tentang hasil Anda.</h2>
        </div>
        <button type="button" className="chat__close" onClick={onClose}>
          Kembali
        </button>
      </header>

      <div
        className="chat__messages"
        ref={listRef}
        aria-live="polite"
      >
        {messages.map((message) => (
          <ChatBubble key={message.id} message={message} />
        ))}
        {pending ? (
          <div className="chat-bubble chat-bubble--assistant chat-bubble--typing" aria-label="Asisten sedang menulis">
            <span />
            <span />
            <span />
          </div>
        ) : null}
      </div>

      <div className="space-y-3">
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
            placeholder="Tulis pertanyaan Anda…"
            aria-label="Tulis pertanyaan Anda"
          />
          <button type="submit" className="btn-primary" disabled={pending || !draft.trim()}>
            Kirim
          </button>
        </form>

        <p className="chat__disclaimer">
          Jawaban asisten bersifat edukatif dan bisa keliru — bukan diagnosis medis.
        </p>
      </div>
    </section>
  );
}
