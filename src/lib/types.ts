export type RiskLevel = "low" | "medium" | "high";
export type BiologicalSex = "female" | "male";
export type YesNoAnswer = "yes" | "no";
export type PriorTbLocation = "pulmonary" | "extrapulmonary" | "unknown";
export type HivStatus = "negative" | "positive" | "unknown";

export interface PatientMetadata {
  sex: BiologicalSex;
  age: number;
  heightCm: number;
  weightKg: number;
  coughDurationDays: number;
  tbPrior: YesNoAnswer;
  tbPriorLocation?: PriorTbLocation;
  fever: YesNoAnswer;
  nightSweats: YesNoAnswer;
  hemoptysis: YesNoAnswer;
  weightLoss: YesNoAnswer;
  smokingLastWeek: YesNoAnswer;
  hivStatus: HivStatus;
  country: string;
  heartRateBpm?: number;
  temperatureC?: number;
}

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
  modelStatus?: "validated" | "candidate";
  /**
   * Whether the model's training data covers the participant's country.
   *
   * A score produced for a country the model was never validated on is not a
   * weaker version of the same answer — it is an extrapolation, and the UI has
   * to say so rather than presenting it like any other result.
   */
  countryValidationStatus?: "in_training_distribution" | "unvalidated_experimental";
  detail?: AnalysisDetail;
}

export type RecordingStatus =
  | "idle"
  | "requesting"
  | "recording"
  | "stopping"
  | "stopped";
