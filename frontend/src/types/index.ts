export interface Job {
  id: string;
  status: string;
  stage: string;
  total?: number;
  indexed?: number;
  thumbnails?: number;
  scored?: number;
  failed?: number;
  processed?: number;
  reused?: number;
  elapsed?: number;
  speed?: number;
  percent?: number;
  current?: string;
  error?: string;
  ai_error?: string;
}
export interface Library {
  id: string;
  name: string;
  source: string;
  created: string;
  budget: number;
  total: number;
  ready: number;
  failed: number;
  selected: number;
  summary: {
    aesthetic: number | null;
    sharpness: number | null;
    exposure: number | null;
  };
  cover: string | null;
  config: { weights: Weights; recursive: boolean };
  job: Job | null;
  highlights?: {
    status: string;
    flickr_count?: number;
    finalist_count?: number;
    embedding_missing?: number;
  };
}
export interface Weights {
  aesthetic: number;
  sharpness: number;
  exposure: number;
}
export interface Photo {
  id: string;
  library_id: string;
  filename: string;
  relative_path: string;
  original_path: string;
  raw_original_path?: string | null;
  raw_relative_path?: string | null;
  raw_filename?: string | null;
  status: string;
  error: string | null;
  provenance: string | null;
  width: number;
  height: number;
  score: number | null;
  taste_affinity?: number | null;
  taste_version?: string | null;
  aesthetic: number | null;
  recommendation: string;
  decision: "auto" | "keep" | "reject" | "review";
  selected: boolean;
  stars: number;
  group_id: string | null;
  group_rank: number | null;
  group_count: number;
  group_protected: boolean;
  explanation: string;
  thumbnail: string | null;
  preview: string | null;
  calibrated: { sharpness?: number; exposure?: number; focus_risk?: string };
  raw: {
    highlight_clipping?: number;
    shadow_clipping?: number;
    contrast?: number;
  };
  metadata: Record<string, string | number>;
  model_id: string | null;
  highlights: HighlightEvidence | null;
}
export interface HighlightEvidence {
  forced_inclusion?: boolean;
  embedding_provenance?: string | null;
  score: number;
  technical: number;
  aesthetic_percentile: number;
  technical_percentile: number;
  distinctiveness: number | null;
  distinctiveness_percentile: number | null;
  strengths: string[];
  uncertainties: string[];
  viable: boolean;
  flickr: boolean;
  auto_flickr: boolean;
  flickr_rank?: number;
  competition_rank: number | null;
  auto_competition_rank: number | null;
  candidate_rank: number | null;
  group_rank: number;
  suppressed_by: string | null;
  diversity_adjustment: number;
  flickr_origin: string;
  competition_origin: string;
  flickr_decision: "auto" | "keep" | "reject";
  competition_decision: "auto" | "include" | "reject" | "alternative";
  model_version: string | null;
  ranking_version: string;
  configuration_version: string;
}
export interface HighlightConfig {
  mode: "general";
  aesthetic_floor: number;
  technical_floor: number;
  flickr_aesthetic_floor: number;
  flickr_percentile: number;
  flickr_max: number | null;
  aesthetic_weight: number;
  technical_weight: number;
  distinctiveness_weight: number;
  diversity_penalty: number;
  force_three: boolean;
}
export interface HighlightsData {
  status: string;
  config: HighlightConfig;
  updated: string;
  summary: {
    flickr_count: number;
    finalist_count: number;
    analysed: number;
    embeddings: number;
    embedding_missing: number;
    viable: number;
    version: string;
    configuration_version: string;
    reason: string | null;
    forced: boolean;
    alternatives: string[];
  };
  flickr: Photo[];
  finalists: Photo[];
  alternatives: Photo[];
}
export interface Photos {
  items: Photo[];
  total: number;
  page: number;
  limit: number;
}
export interface ModelStatus {
  status: string;
  installed: boolean;
  dependencies: boolean;
  error: string | null;
  model_id: string;
  directory: string;
  device: string;
}
