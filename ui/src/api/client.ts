import type {
  Changeset,
  ChangesetListResponse,
  TokenUsage,
  ZoteroStatus,
  ZoteroPapersResponse,
  ZoteroPaperAnnotationsResponse,
  ZoteroPapersCacheStatus,
  ZoteroCollectionsResponse,
} from "../types";

const BASE = "";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function fetchVoid(url: string, options?: RequestInit): Promise<void> {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(await res.text());
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
