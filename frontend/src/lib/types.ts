export type Role = "lead" | "operator" | "reviewer";

export interface Engagement {
  id: string;
  engagement_ref: string;
  client_name: string;
  assessing_org: string;
  authorization_ref: string;
  signature_verified: boolean;
  not_before: string;
  not_after: string;
  status: string;
}

export interface Status {
  locked: boolean;
  now: string;
  engagement: Engagement | null;
  signature_verified: boolean;
}

export interface Decision {
  allowed: boolean;
  reason: string;
  asset_class: string | null;
  intrusive: boolean;
}

export interface ToolInfo {
  name: string;
  required_action: string;
  intrusive: boolean;
  image: string | null;
}

export interface Job {
  id: string;
  engagement_id: string;
  tool: string;
  target: string;
  params: Record<string, unknown>;
  state: string;
  exit_code: number | null;
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Entity {
  id: string;
  type: string;
  dedup_key: string;
  fields: Record<string, unknown>;
  confidence: number;
  first_seen: string;
  last_seen: string;
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  confidence: number;
}
export interface GraphEdge {
  source: string;
  target: string;
}
export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AuditRecord {
  seq: number;
  ts: string;
  operator_id: string | null;
  action: string;
  target: string | null;
  tool: string | null;
  scope_decision: string;
  record_hash: string;
}

export interface Playbook {
  name: string;
  description: string;
  steps: { id: string; action: string; name: string; targets: string }[];
}

export interface WordlistStatus {
  name: string;
  category: string;
  license: string;
  version: string;
  installed: boolean;
  size_bytes: number;
}

export interface JobEvent {
  job_id: string;
  type: "state" | "stdout" | "stderr" | "result" | "error" | "ping";
  data: string;
  ts?: string;
}
