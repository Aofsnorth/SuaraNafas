"use client";

import { useCallback, useState } from "react";
import { analyzeAudio } from "@/lib/api";
import { AnalysisResult } from "@/lib/types";

type AnalysisStatus = "idle" | "uploading" | "analyzing" | "done" | "error";

interface UseAnalysisReturn {
  status: AnalysisStatus;
  result: AnalysisResult | null;
  error: string | null;
  analyze: (blob: Blob, filename?: string) => Promise<AnalysisResult | null>;
  reset: () => void;
}

export function useAnalysis(): UseAnalysisReturn {
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (blob: Blob, filename?: string) => {
    setStatus("uploading");
    setError(null);
    setResult(null);

    try {
      const data = await analyzeAudio(blob, filename);
      setResult(data);
      setStatus("done");
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analisis gagal");
      setStatus("error");
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
  }, []);

  return { status, result, error, analyze, reset };
}
