"use client";

import { useCallback, useState } from "react";
import { AnalysisError, analyzeAudio } from "@/lib/api";
import { getFirebaseAuth } from "@/lib/firebase";
import {
  AnalysisDetail,
  AnalysisResult,
  PatientMetadata,
} from "@/lib/types";

/**
 * "analyzing" was never reachable: the request is a single POST and the UI
 * cannot distinguish "uploading the file" from "server is scoring" because the
 * backend sends no progress signal. Keeping a status the UI can never display
 * invites callers to branch on a value that does not occur.
 */
type AnalysisStatus = "idle" | "uploading" | "done" | "error";

interface UseAnalysisReturn {
  status: AnalysisStatus;
  result: AnalysisResult | null;
  error: string | null;
  /**
   * True when the model refused the request because the participant's country is
   * outside the training distribution. This is a coverage limitation, not a
   * transient failure, so the UI should explain it rather than invite a retry.
   */
  outOfDistribution: boolean;
  analyze: (
    blob: Blob,
    metadata: PatientMetadata,
    filename?: string,
    audioDetail?: Pick<AnalysisDetail, "spectrogram" | "spectrogramSource" | "features">,
    access?: { orderId: string },
  ) => Promise<AnalysisResult | null>;
  reset: () => void;
}

export function useAnalysis(): UseAnalysisReturn {
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outOfDistribution, setOutOfDistribution] = useState(false);

  const analyze = useCallback(async (
    blob: Blob,
    metadata: PatientMetadata,
    filename?: string,
    audioDetail?: Pick<AnalysisDetail, "spectrogram" | "spectrogramSource" | "features">,
    access?: { orderId: string },
  ) => {
    setStatus("uploading");
    setError(null);
    setResult(null);
    setOutOfDistribution(false);

    try {
      // When a paid credit exists the server must be able to verify the caller,
      // so the ID token travels with the request rather than being assumed from
      // client-side auth state.
      let credentials: { token: string; orderId: string } | null = null;
      if (access) {
        const token = await getFirebaseAuth()?.currentUser?.getIdToken(true);
        if (!token) {
          throw new AnalysisError(
            "Sesi masuk tidak tersedia. Silakan masuk kembali.",
            401,
          );
        }
        credentials = { token, orderId: access.orderId };
      }

      const data = await analyzeAudio(blob, metadata, filename, credentials);
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
      // Prefer our own copy of the message: the raw backend string is English
      // and, for the out-of-distribution case, does not say why the refusal is
      // a permanent coverage limitation rather than a bug.
      if (err instanceof AnalysisError) {
        setError(err.userMessage);
        setOutOfDistribution(err.isOutOfDistribution);
      } else {
        setError(err instanceof Error ? err.message : "Analisis gagal");
        setOutOfDistribution(false);
      }
      setStatus("error");
      return null;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
    setOutOfDistribution(false);
  }, []);

  return { status, result, error, outOfDistribution, analyze, reset };
}
