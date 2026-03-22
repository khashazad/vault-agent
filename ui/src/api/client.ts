import type {
  Changeset,
  ChangesetListResponse,
  CostEstimate,
  MigrationJob,
  MigrationNote,
  MigrationNotesResponse,
  MigrationRegistry,
  TaxonomyCurationOp,
  TaxonomyCurationResponse,
  TokenUsage,
  TaxonomyProposal,
  VaultConfigResponse,
  VaultHistoryEntry,
  VaultPickerResponse,
  VaultTaxonomy,
  ZoteroStatus,
  ZoteroPapersResponse,
  ZoteroPaperAnnotationsResponse,
  ZoteroPapersCacheStatus,
  ZoteroCollectionsResponse,
} from "../types";

const BASE = "";

async function extractError(res: Response): Promise<string> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      const body = await res.json();
      return body.detail ?? body.message ?? JSON.stringify(body);
    } catch {
      // fall through
    }
  }
  if (contentType.includes("text/html")) {
    return `Server returned HTML instead of JSON (HTTP ${res.status}). Is the backend running?`;
  }
  const text = await res.text();
  return text.length > 200 ? text.slice(0, 200) + "..." : text;
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await extractError(res));
  return res.json();
}

async function fetchVoid(url: string, options?: RequestInit): Promise<void> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await extractError(res));
}

export function fetchChangesets(opts?: {
  status?: string;
  offset?: number;
  limit?: number;
}): Promise<ChangesetListResponse> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.offset) params.set("offset", String(opts.offset));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetchJSON(`${BASE}/changesets${qs ? `?${qs}` : ""}`);
}

export function fetchChangeset(id: string): Promise<Changeset> {
  return fetchJSON(`${BASE}/changesets/${id}`);
}

export async function fetchChangesetCost(
  id: string,
): Promise<TokenUsage | null> {
  const cs = await fetchJSON<Changeset>(`${BASE}/changesets/${id}`);
  return cs.usage ?? null;
}

export function updateChangeStatus(
  changesetId: string,
  changeId: string,
  status: "approved" | "rejected",
): Promise<void> {
  return fetchVoid(`${BASE}/changesets/${changesetId}/changes/${changeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function applyChangeset(
  changesetId: string,
  changeIds?: string[],
): Promise<{ applied: string[]; failed: { id: string; error: string }[] }> {
  return fetchJSON(`${BASE}/changesets/${changesetId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changeIds ? { change_ids: changeIds } : {}),
  });
}

export function rejectChangeset(changesetId: string): Promise<void> {
  return fetchVoid(`${BASE}/changesets/${changesetId}/reject`, {
    method: "POST",
  });
}

export function deleteChangeset(changesetId: string): Promise<void> {
  return fetchVoid(`${BASE}/changesets/${changesetId}`, {
    method: "DELETE",
  });
}

export function fetchZoteroStatus(): Promise<ZoteroStatus> {
  return fetchJSON(`${BASE}/zotero/status`);
}

export function fetchZoteroPapers(opts?: {
  collectionKey?: string;
  offset?: number;
  limit?: number;
  search?: string;
  syncStatus?: string;
}): Promise<ZoteroPapersResponse> {
  const params = new URLSearchParams();
  if (opts?.collectionKey) params.set("collection_key", opts.collectionKey);
  if (opts?.offset) params.set("offset", String(opts.offset));
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.search) params.set("search", opts.search);
  if (opts?.syncStatus) params.set("sync_status", opts.syncStatus);
  const qs = params.toString();
  return fetchJSON(`${BASE}/zotero/papers${qs ? `?${qs}` : ""}`);
}

export function fetchZoteroPapersCacheStatus(): Promise<ZoteroPapersCacheStatus> {
  return fetchJSON(`${BASE}/zotero/papers/cache-status`);
}

export function triggerZoteroPapersRefresh(): Promise<void> {
  return fetchVoid(`${BASE}/zotero/papers/refresh`, { method: "POST" });
}

export function fetchZoteroCollections(): Promise<ZoteroCollectionsResponse> {
  return fetchJSON(`${BASE}/zotero/collections`);
}

export function fetchZoteroPaperAnnotations(
  paperKey: string,
): Promise<ZoteroPaperAnnotationsResponse> {
  return fetchJSON(`${BASE}/zotero/papers/${paperKey}/annotations`);
}

export function syncZoteroPaper(
  paperKey: string,
  excludedAnnotationKeys?: string[],
  model?: string,
): Promise<Changeset> {
  return fetchJSON(`${BASE}/zotero/papers/${paperKey}/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      paper_key: paperKey,
      excluded_annotation_keys: excludedAnnotationKeys ?? null,
      model: model ?? "sonnet",
    }),
  });
}

export function requestChanges(
  changesetId: string,
  feedback: string,
): Promise<{ id: string; status: string; feedback: string }> {
  return fetchJSON(`${BASE}/changesets/${changesetId}/request-changes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export function regenerateChangeset(changesetId: string): Promise<Changeset> {
  return fetchJSON(`${BASE}/changesets/${changesetId}/regenerate`, {
    method: "POST",
  });
}

export function updateChangeContent(
  changesetId: string,
  changeId: string,
  proposedContent: string,
): Promise<void> {
  return fetchVoid(`${BASE}/changesets/${changesetId}/changes/${changeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proposed_content: proposedContent }),
  });
}

// --- Vault config API ---

export function fetchVaultConfig(): Promise<VaultConfigResponse> {
  return fetchJSON(`${BASE}/vault/config`);
}

export function setVaultConfig(
  vaultPath: string,
): Promise<VaultConfigResponse> {
  return fetchJSON(`${BASE}/vault/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vault_path: vaultPath }),
  });
}

export function openVaultPicker(): Promise<VaultPickerResponse> {
  return fetchJSON(`${BASE}/vault/picker`, { method: "POST" });
}

export function fetchVaultHistory(): Promise<{
  vaults: VaultHistoryEntry[];
}> {
  return fetchJSON(`${BASE}/vault/history`);
}

export function deleteVaultHistory(path: string): Promise<void> {
  const params = new URLSearchParams({ path });
  return fetchVoid(`${BASE}/vault/history?${params.toString()}`, {
    method: "DELETE",
  });
}

// --- Migration API ---

export function estimateMigrationCost(
  model?: string,
  taxonomyId?: string,
): Promise<CostEstimate> {
  const params = new URLSearchParams();
  if (model) params.set("model", model);
  if (taxonomyId) params.set("taxonomy_id", taxonomyId);
  const qs = params.toString();
  return fetchJSON(`${BASE}/migration/estimate${qs ? `?${qs}` : ""}`, {
    method: "POST",
  });
}

export function importTaxonomy(
  data: Record<string, unknown>,
): Promise<TaxonomyProposal> {
  return fetchJSON(`${BASE}/migration/taxonomy/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function fetchTaxonomy(id: string): Promise<TaxonomyProposal> {
  return fetchJSON(`${BASE}/migration/taxonomy/${id}`);
}

export function updateTaxonomy(
  id: string,
  updates: Partial<TaxonomyProposal>,
): Promise<TaxonomyProposal> {
  return fetchJSON(`${BASE}/migration/taxonomy/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export function activateTaxonomy(id: string): Promise<TaxonomyProposal> {
  return fetchJSON(`${BASE}/migration/taxonomy/${id}/activate`, {
    method: "POST",
  });
}

export function createMigrationJob(
  targetVault: string,
  taxonomyId?: string,
  model?: string,
  batch?: boolean,
): Promise<MigrationJob> {
  return fetchJSON(`${BASE}/migration/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_vault: targetVault,
      taxonomy_id: taxonomyId,
      model: model ?? "sonnet",
      batch: batch ?? true,
    }),
  });
}

export function fetchMigrationJob(id: string): Promise<MigrationJob> {
  return fetchJSON(`${BASE}/migration/jobs/${id}`);
}

export function fetchMigrationNotes(
  jobId: string,
  opts?: { status?: string; offset?: number; limit?: number },
): Promise<MigrationNotesResponse> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.offset) params.set("offset", String(opts.offset));
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetchJSON(
    `${BASE}/migration/jobs/${jobId}/notes${qs ? `?${qs}` : ""}`,
  );
}

export function updateMigrationNote(
  jobId: string,
  noteId: string,
  updates: { status?: string; proposed_content?: string },
): Promise<MigrationNote> {
  return fetchJSON(`${BASE}/migration/jobs/${jobId}/notes/${noteId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export function applyMigration(
  jobId: string,
): Promise<{ applied: string[]; failed: { id: string; error: string }[] }> {
  return fetchJSON(`${BASE}/migration/jobs/${jobId}/apply`, {
    method: "POST",
  });
}

export function cancelMigration(
  jobId: string,
): Promise<{ id: string; status: string }> {
  return fetchJSON(`${BASE}/migration/jobs/${jobId}/cancel`, {
    method: "POST",
  });
}

export function fetchMigrationJobs(opts?: {
  status?: string;
  limit?: number;
}): Promise<{ jobs: MigrationJob[] }> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetchJSON(`${BASE}/migration/jobs${qs ? `?${qs}` : ""}`);
}

export function resumeMigration(
  jobId: string,
  model?: string,
): Promise<MigrationJob> {
  return fetchJSON(`${BASE}/migration/jobs/${jobId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: model ?? "sonnet" }),
  });
}

export function retryMigrationNote(
  jobId: string,
  noteId: string,
  model?: string,
): Promise<MigrationNote> {
  return fetchJSON(`${BASE}/migration/jobs/${jobId}/notes/${noteId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: model ?? "sonnet" }),
  });
}

export function fetchMigrationRegistry(): Promise<MigrationRegistry> {
  return fetchJSON(`${BASE}/migration/registry`);
}

// --- Vault taxonomy API ---

export function fetchVaultTaxonomy(): Promise<VaultTaxonomy> {
  return fetchJSON(`${BASE}/vault/taxonomy`);
}

export function applyTaxonomyCuration(
  operations: TaxonomyCurationOp[],
): Promise<TaxonomyCurationResponse> {
  return fetchJSON(`${BASE}/vault/taxonomy/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operations }),
  });
}
