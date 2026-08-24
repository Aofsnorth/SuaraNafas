"use client";

import { useCallback, useState } from "react";

export type ResultFlowStage = "idle" | "prompt" | "detail" | "chat";

interface UseResultFlowReturn {
  stage: ResultFlowStage;
  openPrompt: () => void;
  showDetail: () => void;
  showChat: () => void;
  backToPrompt: () => void;
  close: () => void;
}

export function useResultFlow(): UseResultFlowReturn {
  const [stage, setStage] = useState<ResultFlowStage>("idle");

  const openPrompt = useCallback(() => setStage("prompt"), []);
  const showDetail = useCallback(() => setStage("detail"), []);
  const showChat = useCallback(() => setStage("chat"), []);
  const backToPrompt = useCallback(() => setStage("prompt"), []);
  const close = useCallback(() => setStage("idle"), []);

  return { stage, openPrompt, showDetail, showChat, backToPrompt, close };
}
