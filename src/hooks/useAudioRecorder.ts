"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RecordingStatus } from "@/lib/types";

interface UseAudioRecorderReturn {
  status: RecordingStatus;
  blob: Blob | null;
  error: string | null;
  duration: number;
  analyser: AnalyserNode | null;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [status, setStatus] = useState<RecordingStatus>("idle");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (
      audioContextRef.current &&
      audioContextRef.current.state !== "closed"
    ) {
      audioContextRef.current.close().catch(() => null);
    }
    streamRef.current = null;
    mediaRecorderRef.current = null;
    audioContextRef.current = null;
    setAnalyser(null);
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setBlob(null);
    setError(null);
    setDuration(0);
    setStatus("idle");
    chunksRef.current = [];
  }, [cleanup]);

  const start = useCallback(async () => {
    reset();
    setStatus("requesting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 256;
      source.connect(analyserNode);
      setAnalyser(analyserNode);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : undefined;

      const mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const recordedBlob = new Blob(chunksRef.current, {
          type: mediaRecorder.mimeType || "audio/webm",
        });
        setBlob(recordedBlob);
        setStatus("stopped");
        cleanup();
      };

      mediaRecorder.onerror = () => {
        setError("Terjadi kesalahan saat merekam audio.");
        setStatus("idle");
        cleanup();
      };

      mediaRecorder.start();
      startedAtRef.current = Date.now();
      setStatus("recording");
      setDuration(0);
      timerRef.current = window.setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAtRef.current) / 1000);
        setDuration(seconds);
      }, 250);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Tidak bisa mengakses mikrofon. Pastikan izin diberikan.",
      );
      setStatus("idle");
      cleanup();
    }
  }, [cleanup, reset]);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      setStatus("stopping");
      mediaRecorderRef.current.stop();
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return { status, blob, error, duration, analyser, start, stop, reset };
}
