"use client";

import dynamic from "next/dynamic";

const AudioRecorder = dynamic(
  () => import("@/components/AudioRecorder").then((module) => module.AudioRecorder),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-112 animate-pulse rounded-xl border border-rule bg-paper-2/40" />
    ),
  },
);

export function AnalyzeClient() {
  return <AudioRecorder />;
}
