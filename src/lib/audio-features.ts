import { AnalysisFeature } from "./types";

const FREQUENCY_BIN_COUNT = 24;
const TIME_SLICE_COUNT = 32;
const FFT_SIZE = 512;

interface AudioVisualizationDetail {
  spectrogram: number[][];
  features: AnalysisFeature[];
  uploadBlob: Blob;
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

function encodeMonoWav(samples: Float32Array, sampleRate: number) {
  const headerSize = 44;
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(headerSize + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  const writeText = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    const value = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    view.setInt16(headerSize + index * bytesPerSample, value, true);
  });

  return new Blob([buffer], { type: "audio/wav" });
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
      uploadBlob: encodeMonoWav(samples, audioBuffer.sampleRate),
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
