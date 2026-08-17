export type User = { id: number; name: string; email: string; role: string; scopes: string[]; organization: string };
export type WorkItem = {
  id: number;
  title: string;
  customer_name: string;
  asset_ref: string;
  status: string;
  context: Record<string, string>;
  pending_actions: number;
  updated_at: string;
};
export type ArtifactSection = { heading: string; body: string; citations: string[] };
export type DecisionSignals = {
  provider?: string | null;
  model?: string | null;
  case_type?: string | null;
  case_type_confidence?: number | null;
  priority_score?: number | null;
  onsite_probability?: number | null;
};
export type SecuritySignals = {
  provider?: string | null;
  model?: string | null;
  verdict?: string | null;
  request_category?: string | null;
  category_confidence?: number | null;
  malicious_probability?: number | null;
  block_probability?: number | null;
  needs_human_review?: number | null;
};
export type Artifact = {
  title: string;
  summary: string;
  sections: ArtifactSection[];
  next_steps: string[];
  citations: string[];
  decision_signals?: DecisionSignals;
  security_signals?: SecuritySignals;
  action_proposal?: Record<string, unknown> | null;
};
