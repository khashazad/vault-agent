import type {
  Changeset,
  ChangesetSummary,
  SearchResponse,
  HighlightInput,
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

export function previewHighlight(highlight: HighlightInput): Promise<Changeset> {
  return fetchJSON(`${BASE}/highlights/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(highlight),
  });
}

export function fetchChangesets(): Promise<ChangesetSummary[]> {
  return fetchJSON(`${BASE}/changesets`);
}

export function fetchChangeset(id: string): Promise<Changeset> {
  return fetchJSON(`${BASE}/changesets/${id}`);
}

export function updateChangeStatus(
  changesetId: string,
  changeId: string,
  status: "approved" | "rejected"
): Promise<void> {
  return fetchVoid(
    `${BASE}/changesets/${changesetId}/changes/${changeId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }
  );
}

export function applyChangeset(
  changesetId: string,
  changeIds?: string[]
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

export function regenerateChangeset(
  changesetId: string,
  feedback: string
): Promise<Changeset> {
  return fetchJSON(`${BASE}/changesets/${changesetId}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
}

export function searchVault(query: string, n = 10): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, n: String(n) });
  return fetchJSON(`${BASE}/vault/search?${params}`);
}
