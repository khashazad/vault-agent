export type SourceType = "web" | "zotero" | "book";

export interface SourceMetadata {
  title?: string;
  // zotero
  doi?: string;
  authors?: string[];
  year?: string;
  publication_title?: string;
  abstract?: string;
  paper_key?: string;
  // book
  isbn?: string;
  chapter?: string;
  page_range?: string;
  // web
  url?: string;
  site_name?: string;
}

export interface ContentItem {
  text: string;
  source: string;
  annotation?: string;
  color?: string;
  source_type?: SourceType;
  source_metadata?: SourceMetadata;
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
  action: "update" | "create" | "skip";
  target_path: string | null;
  reasoning: string;
  confidence: number;
  search_results_used: number;
  additional_targets: string[] | null;
  duplicate_notes: string[] | null;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_write_tokens: number;
  cache_read_tokens: number;
  api_calls: number;
  tool_calls: number;
  is_batch: boolean;
  model: string;
  total_cost_usd: number;
}

export interface Changeset {
  id: string;
  items: ContentItem[];
  changes: ProposedChange[];
  reasoning: string;
  status: "pending" | "applied" | "rejected" | "partially_applied" | "skipped";
  created_at: string;
  source_type: SourceType;
  routing: RoutingInfo | null;
  usage: TokenUsage | null;
  feedback: string | null;
  parent_changeset_id: string | null;
}

export interface ZoteroSyncRequest {
  collection_key?: string;
  paper_keys?: string[];
  full_sync?: boolean;
}

export interface ZoteroSyncResponse {
  papers_found: number;
  papers_processed: number;
  changeset_ids: string[];
  skipped_papers: string[];
  library_version: number;
}

export interface ZoteroStatus {
  configured: boolean;
  last_version: number | null;
  last_synced: string | null;
}

export interface ZoteroPaperSummary {
  key: string;
  title: string;
  authors: string[];
  year: string;
  item_type: string;
  last_synced: string | null;
  changeset_id: string | null;
  annotation_count: number | null;
}

export interface ZoteroPapersResponse {
  papers: ZoteroPaperSummary[];
  total: number;
  cache_updated_at: string | null;
}

export interface ZoteroPapersCacheStatus {
  cached_count: number;
  cache_updated_at: string | null;
  sync_in_progress: boolean;
}

export interface ZoteroAnnotationItem {
  key: string;
  text: string;
  comment: string;
  color: string;
  page_label: string;
  annotation_type: string;
  date_added: string;
}

export interface ZoteroPaperAnnotationsResponse {
  paper_key: string;
  paper_title: string;
  annotations: ZoteroAnnotationItem[];
  total: number;
}

export interface ZoteroCollection {
  key: string;
  name: string;
  parent_collection: string | null;
  num_items: number;
  num_collections: number;
}

export interface ZoteroCollectionsResponse {
  collections: ZoteroCollection[];
  total: number;
}
