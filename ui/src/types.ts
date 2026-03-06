export interface HighlightInput {
  text: string;
  source: string;
  annotation?: string;
}

export interface ProposedChange {
  id: string;
  tool_name: string;
  input: Record<string, unknown>;
  original_content: string | null;
  proposed_content: string;
  diff: string;
  status: "pending" | "approved" | "rejected";
}

export interface RoutingInfo {
  action: "update" | "create";
  target_path: string | null;
  reasoning: string;
  confidence: number;
  search_results_used: number;
  additional_targets: string[] | null;
}

export interface Changeset {
  id: string;
  highlights: HighlightInput[];
  /** @deprecated Use highlights[0] — kept for backward compat */
  highlight: HighlightInput;
  changes: ProposedChange[];
  reasoning: string;
  status: "pending" | "applied" | "rejected" | "partially_applied";
  created_at: string;
  routing: RoutingInfo | null;
  feedback: string | null;
  parent_changeset_id: string | null;
}

export interface ChangesetSummary {
  id: string;
  source: string;
  highlight_count: number;
  change_count: number;
  status: string;
  created_at: string;
  routing_action: "update" | "create" | null;
  routing_target: string | null;
  routing_confidence: number | null;
}

export interface ChunkInfo {
  note_path: string;
  heading: string;
  content: string;
  score: number;
  search_type: string;
}

export interface SearchResponse {
  query: string;
  results: ChunkInfo[];
  count: number;
  embedding_model: string;
  vector_dimensions: number;
  search_type: string;
}
