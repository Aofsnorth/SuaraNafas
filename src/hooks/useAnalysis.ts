"use client";

import { useCallback, useState } from "react";
import { analyzeAudio } from "@/lib/api";
import {
  AnalysisDetail,
  AnalysisResult,
  BiologicalSex,
} from "@/lib/types";

type AnalysisStatus = "idle" | "uploading" | "analyzing" | "done" | "error";

interface UseAnalysisReturn {
  status: AnalysisStatus;
  result: AnalysisResult | null;
  error: string | null;
  analyze: (
    blob: Blob,
    sex: BiologicalSex,
    filename?: string,
    audioDetail?: Pick<AnalysisDetail, "spectrogram" | "spectrogramSource" | "features">,
  ) => Promise<AnalysisResult | null>;
  reset: () => void;
}

export function useAnalysis(): UseAnalysisReturn {
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (
    blob: Blob,
    sex: BiologicalSex,
    filename?: string,
    audioDetail?: Pick<AnalysisDetail, "spectrogram" | "spectrogramSource" | "features">,
  ) => {
    setStatus("uploading");
    setError(null);
    setResult(null);

    try {
      const data = await analyzeAudio(blob, sex, filename);
      const resultWithAudioDetail: AnalysisResult = audioDetail
        ? {
            ...data,
            detail: {
              scores: data.detail?.scores ?? [],
              ...data.detail,
              ...audioDetail,
            },
          }
        : data;
      setResult(resultWithAudioDetail);
      setStatus("done");
      return resultWithAudioDetail;
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
