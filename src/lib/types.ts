export type RiskLevel = "low" | "medium" | "high";
export type BiologicalSex = "female" | "male";

export interface AnalysisScore {
  label: string;
  value: number;
}

export interface AnalysisFeature {
  label: string;
  value: string;
}

export interface AnalysisModelMeta {
  name: string;
  version: string;
  durationMs: number;
}

export interface AnalysisDetail {
  scores: AnalysisScore[];
  spectrogram?: number[][];
  spectrogramSource?: "audio" | "backend";
  features?: AnalysisFeature[];
  model?: AnalysisModelMeta;
}

export interface AnalysisResult {
  risk: RiskLevel;
  confidence: number;
  message: string;
  recommendation: string;
  source?: "mock" | "backend";
  detail?: AnalysisDetail;
}

export interface AnalysisError {
  error: string;
}

export type RecordingStatus =
  | "idle"
  | "requesting"
  | "recording"
  | "stopping"
  | "stopped";
