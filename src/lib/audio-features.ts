import { AnalysisFeature } from "./types";

const FREQUENCY_BIN_COUNT = 24;
const TIME_SLICE_COUNT = 32;
const FFT_SIZE = 512;

interface AudioVisualizationDetail {
  spectrogram: number[][];
  features: AnalysisFeature[];
}

function createHannWindow(size: number) {
  return Float32Array.from(
    { length: size },
    (_, index) => 0.5 - 0.5 * Math.cos((2 * Math.PI * index) / (size - 1)),
  );
}

function calculateFrequencyMagnitude(
  samples: Float32Array,
  start: number,
  frequencyBin: number,
  window: Float32Array,
) {
  let real = 0;
  let imaginary = 0;
  const angularStep = (2 * Math.PI * frequencyBin) / FFT_SIZE;

  for (let index = 0; index < FFT_SIZE; index += 1) {
    const sample = (samples[start + index] ?? 0) * window[index];
    const angle = angularStep * index;
    real += sample * Math.cos(angle);
    imaginary -= sample * Math.sin(angle);
  }

  return Math.sqrt(real * real + imaginary * imaginary);
}

export function buildSpectrogram(samples: Float32Array) {
  const paddedLength = Math.max(samples.length, FFT_SIZE);
  const hopSize = Math.max(
    1,
    Math.floor((paddedLength - FFT_SIZE) / Math.max(1, TIME_SLICE_COUNT - 1)),
  );
  const window = createHannWindow(FFT_SIZE);
  const timeSlices: number[][] = [];
  let maximumMagnitude = 0;

  for (let timeIndex = 0; timeIndex < TIME_SLICE_COUNT; timeIndex += 1) {
    const start = Math.min(
      Math.max(0, samples.length - FFT_SIZE),
      timeIndex * hopSize,
    );
    const slice = Array.from({ length: FREQUENCY_BIN_COUNT }, (_, binIndex) => {
      const fftBin = Math.max(1, Math.round(((binIndex + 1) / FREQUENCY_BIN_COUNT) ** 1.7 * 190));
      const magnitude = calculateFrequencyMagnitude(samples, start, fftBin, window);
      maximumMagnitude = Math.max(maximumMagnitude, magnitude);
      return magnitude;
    });
    timeSlices.push(slice);
  }

  const normalizer = Math.log1p(maximumMagnitude) || 1;
  return Array.from({ length: FREQUENCY_BIN_COUNT }, (_, rowIndex) =>
    timeSlices.map((slice) =>
      Number((Math.log1p(slice[rowIndex]) / normalizer).toFixed(3)),
    ),
  ).reverse();
}

export async function extractAudioVisualization(
  blob: Blob,
): Promise<AudioVisualizationDetail> {
  const AudioContextClass = window.AudioContext;
  const audioContext = new AudioContextClass();

  try {
    const audioBuffer = await audioContext.decodeAudioData(await blob.arrayBuffer());
    const samples = new Float32Array(audioBuffer.length);

    for (let channel = 0; channel < audioBuffer.numberOfChannels; channel += 1) {
      const channelData = audioBuffer.getChannelData(channel);
      for (let index = 0; index < channelData.length; index += 1) {
        samples[index] += channelData[index] / audioBuffer.numberOfChannels;
      }
    }

    return {
      spectrogram: buildSpectrogram(samples),
      features: [
        { label: "Durasi audio", value: `${audioBuffer.duration.toFixed(1)} dtk` },
        { label: "Sample rate", value: `${audioBuffer.sampleRate.toLocaleString("id-ID")} Hz` },
        { label: "Kanal", value: `${audioBuffer.numberOfChannels}` },
      ],
    };
  } catch {
    throw new Error(
      "Audio tidak dapat dibaca untuk membuat spektrogram. Coba rekam ulang atau unggah WAV/WebM.",
    );
  } finally {
    await audioContext.close().catch(() => undefined);
  }
}
