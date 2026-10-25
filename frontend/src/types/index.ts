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
  status: string;
  error: string | null;
  provenance: string | null;
  width: number;
  height: number;
  score: number | null;
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
