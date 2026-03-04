import type { Changeset, ChangesetSummary, SearchResponse } from "../types";

const BASE = "";

export async function fetchChangesets(): Promise<ChangesetSummary[]> {
  const res = await fetch(`${BASE}/changesets`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchChangeset(id: string): Promise<Changeset> {
  const res = await fetch(`${BASE}/changesets/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function updateChangeStatus(
  changesetId: string,
  changeId: string,
  status: "approved" | "rejected"
): Promise<void> {
  const res = await fetch(
    `${BASE}/changesets/${changesetId}/changes/${changeId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }
  );
  if (!res.ok) throw new Error(await res.text());
}

export async function applyChangeset(
  changesetId: string,
  changeIds?: string[]
): Promise<{ applied: string[]; failed: { id: string; error: string }[] }> {
  const res = await fetch(`${BASE}/changesets/${changesetId}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changeIds ? { change_ids: changeIds } : {}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function rejectChangeset(changesetId: string): Promise<void> {
  const res = await fetch(`${BASE}/changesets/${changesetId}/reject`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function searchVault(query: string, n = 10): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, n: String(n) });
  const res = await fetch(`/vault/search?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
