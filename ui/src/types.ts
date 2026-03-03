export interface HighlightInput {
  text: string;
  source: string;
  annotation?: string;
  tags?: string[];
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

export interface Changeset {
  id: string;
  highlight: HighlightInput;
  changes: ProposedChange[];
  reasoning: string;
  status: "pending" | "applied" | "rejected" | "partially_applied";
  created_at: string;
}

export interface ChangesetSummary {
  id: string;
  source: string;
  change_count: number;
  status: string;
  created_at: string;
}

export interface AgentStreamEvent {
  type:
    | "reasoning"
    | "tool_call"
    | "tool_result"
    | "proposed_change"
    | "complete"
    | "error";
  data: Record<string, unknown>;
}
