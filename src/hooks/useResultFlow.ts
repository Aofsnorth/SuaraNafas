"use client";

import { useCallback, useState } from "react";
import { AnalysisResult } from "@/lib/types";

export type ResultFlowStage = "idle" | "prompt" | "detail" | "chat";

export function isHighRiskResult(result: AnalysisResult | null): boolean {
  return result?.risk === "high";
}

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
