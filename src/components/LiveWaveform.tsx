"use client";

import { useEffect, useRef } from "react";

interface LiveWaveformProps {
  analyser: AnalyserNode | null;
  isActive: boolean;
}

const POINT_COUNT = 72;
const VIEW_WIDTH = 100;
const VIEW_HEIGHT = 50;
const CENTER_Y = VIEW_HEIGHT / 2;

function buildWavePath(
  phase: number,
  audioData: Uint8Array<ArrayBuffer> | null,
) {
  const points = Array.from({ length: POINT_COUNT }, (_, index) => {
    const progress = index / (POINT_COUNT - 1);
    const idleWave =
      Math.sin(progress * Math.PI * 4 + phase) * 3.8 +
      Math.sin(progress * Math.PI * 8 - phase * 0.55) * 1.15;
    const sampleIndex = audioData
      ? Math.min(audioData.length - 1, Math.floor(progress * audioData.length))
      : 0;
    const audioWave = audioData ? ((audioData[sampleIndex] ?? 128) - 128) / 128 : 0;
    const edgeEnvelope = Math.sin(progress * Math.PI) ** 0.35;
    const y = CENTER_Y + idleWave + audioWave * 9 * edgeEnvelope;

    return `${(progress * VIEW_WIDTH).toFixed(2)},${y.toFixed(2)}`;
  });

  return `M${points.join(" L")}`;
}

export function LiveWaveform({ analyser, isActive }: LiveWaveformProps) {
  const glowPathRef = useRef<SVGPathElement>(null);
  const tracePathRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const audioData = analyser
      ? new Uint8Array(new ArrayBuffer(analyser.fftSize))
      : null;
    let frameId = 0;
    let phase = 0;
    let previousTime = performance.now();

    const draw = (time: number) => {
      const elapsed = Math.min(time - previousTime, 32);
      previousTime = time;

      if (!reducedMotion) {
        phase = (phase + (elapsed / 3600) * Math.PI * 2) % (Math.PI * 2);
      }

      if (audioData && analyser && isActive) {
        analyser.getByteTimeDomainData(audioData);
      } else if (audioData) {
        audioData.fill(128);
      }

      const path = buildWavePath(phase, isActive ? audioData : null);
      glowPathRef.current?.setAttribute("d", path);
      tracePathRef.current?.setAttribute("d", path);

      if (!reducedMotion) frameId = requestAnimationFrame(draw);
    };

    draw(previousTime);

    return () => cancelAnimationFrame(frameId);
  }, [analyser, isActive]);

  return (
    <figure
      className="live-waveform"
      data-active={isActive ? "true" : "false"}
      aria-label={
        isActive
          ? "Visualisasi gelombang audio rekaman aktif"
          : "Visualisasi gelombang audio dalam keadaan siap"
      }
    >
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        preserveAspectRatio="none"
        className="live-waveform__canvas"
        aria-hidden="true"
      >
        <path ref={glowPathRef} className="live-waveform__glow" />
        <path ref={tracePathRef} className="live-waveform__trace" />
      </svg>
    </figure>
  );
}
