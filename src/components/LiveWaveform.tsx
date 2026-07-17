"use client";

import { useEffect, useRef } from "react";

interface LiveWaveformProps {
  analyser: AnalyserNode | null;
  isActive: boolean;
}

const BAR_COUNT = 48;

function resizeCanvas(canvas: HTMLCanvasElement) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const bounds = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(bounds.width * ratio));
  const height = Math.max(1, Math.round(bounds.height * ratio));

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  return { width, height, ratio };
}

export function LiveWaveform({ analyser, isActive }: LiveWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const frequencyData = analyser
      ? new Uint8Array(analyser.frequencyBinCount)
      : null;
    const timeData = analyser ? new Uint8Array(analyser.fftSize) : null;
    let frameId = 0;

    const draw = () => {
      const { width, height, ratio } = resizeCanvas(canvas);
      context.clearRect(0, 0, width, height);

      const styles = getComputedStyle(canvas);
      const accent = styles.getPropertyValue("--color-accent").trim() || "#5eead4";
      const muted = styles.getPropertyValue("--color-rule-2").trim() || "#334155";

      if (analyser && frequencyData && timeData && isActive) {
        analyser.getByteFrequencyData(frequencyData);
        analyser.getByteTimeDomainData(timeData);
      } else {
        frequencyData?.fill(0);
        timeData?.fill(128);
      }

      const barGap = 2 * ratio;
      const barWidth = Math.max(1.5 * ratio, (width - barGap * (BAR_COUNT - 1)) / BAR_COUNT);
      const usableHeight = height * 0.66;

      for (let index = 0; index < BAR_COUNT; index += 1) {
        const dataIndex = frequencyData
          ? Math.min(
              frequencyData.length - 1,
              Math.round(((index + 1) / BAR_COUNT) ** 1.7 * frequencyData.length * 0.72),
            )
          : 0;
        const level = frequencyData ? (frequencyData[dataIndex] ?? 0) / 255 : 0;
        const idleLevel = isActive ? 0 : 0.025 + Math.sin(index * 0.55) * 0.012;
        const barHeight = Math.max(2 * ratio, (level + idleLevel) * usableHeight);
        const x = index * (barWidth + barGap);
        const y = height - barHeight;

        context.globalAlpha = isActive ? 0.28 + level * 0.72 : 0.26;
        context.fillStyle = isActive ? accent : muted;
        context.fillRect(x, y, barWidth, barHeight);
      }

      context.globalAlpha = isActive ? 0.95 : 0.45;
      context.strokeStyle = isActive ? accent : muted;
      context.lineWidth = 1.4 * ratio;
      context.beginPath();

      const samples = timeData ?? new Uint8Array(128).fill(128);
      for (let index = 0; index < samples.length; index += 1) {
        const x = (index / Math.max(1, samples.length - 1)) * width;
        const amplitude = ((samples[index] ?? 128) - 128) / 128;
        const y = height * 0.34 + amplitude * height * 0.2;
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();
      context.globalAlpha = 1;

      frameId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(frameId);
  }, [analyser, isActive]);

  return (
    <figure
      className="live-waveform"
      data-active={isActive ? "true" : "false"}
      aria-label={
        isActive
          ? "Spektrum frekuensi dan gelombang audio mikrofon secara langsung"
          : "Visualisasi audio dalam keadaan siap"
      }
    >
      <canvas ref={canvasRef} className="live-waveform__canvas" aria-hidden="true" />
      <figcaption className="live-waveform__caption">
        {isActive ? "Spektrum mikrofon langsung" : ""}
      </figcaption>
    </figure>
  );
}
