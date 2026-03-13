import { describe, it, expect } from "vitest";
import {
  fetchChangeset,
  fetchChangesets,
  applyChangeset,
  rejectChangeset,
  updateChangeStatus,
  requestChanges,
  regenerateChangeset,
  updateChangeContent,
  fetchZoteroStatus,
  fetchZoteroPapers,
  fetchZoteroCollections,
  fetchZoteroPaperAnnotations,
  syncZoteroPaper,
  fetchZoteroPapersCacheStatus,
  triggerZoteroPapersRefresh,
} from "../../api/client";

describe("API client", () => {
  it("fetchChangeset calls correct URL", async () => {
    const cs = await fetchChangeset("cs-123");
    expect(cs.id).toBeDefined();
  });

  it("applyChangeset sends POST", async () => {
    const result = await applyChangeset("cs-123");
    expect(result.applied).toContain("change-1");
    expect(result.failed).toEqual([]);
  });

  it("rejectChangeset sends POST", async () => {
    // Should not throw
    await expect(rejectChangeset("cs-123")).resolves.toBeUndefined();
  });

  it("updateChangeStatus sends PATCH", async () => {
    // Should not throw
    await expect(
      updateChangeStatus("cs-123", "change-1", "approved"),
    ).resolves.toBeUndefined();
  });

  it("fetchZoteroStatus returns status", async () => {
    const status = await fetchZoteroStatus();
    expect(status.configured).toBe(true);
  });

  it("fetchZoteroPapers returns papers", async () => {
    const resp = await fetchZoteroPapers();
    expect(resp.papers.length).toBeGreaterThan(0);
    expect(resp.total).toBe(1);
  });

  it("fetchZoteroCollections returns collections", async () => {
    const resp = await fetchZoteroCollections();
    expect(resp.collections.length).toBeGreaterThan(0);
  });

  it("fetchZoteroPaperAnnotations returns annotations", async () => {
    const resp = await fetchZoteroPaperAnnotations("PAPER1");
    expect(resp.annotations.length).toBe(1);
  });

  it("syncZoteroPaper returns changeset", async () => {
    const cs = await syncZoteroPaper("PAPER1");
    expect(cs.id).toBeDefined();
  });

  it("fetchZoteroPapersCacheStatus returns cache info", async () => {
    const resp = await fetchZoteroPapersCacheStatus();
    expect(resp.cached_count).toBe(10);
  });

  it("triggerZoteroPapersRefresh completes", async () => {
    await expect(triggerZoteroPapersRefresh()).resolves.toBeUndefined();
  });

  it("fetchChangesets returns list", async () => {
    const resp = await fetchChangesets();
    expect(resp.changesets.length).toBeGreaterThan(0);
    expect(resp.total).toBe(1);
  });

  it("requestChanges returns updated status", async () => {
    const resp = await requestChanges("cs-123", "Fix heading");
    expect(resp.status).toBe("revision_requested");
    expect(resp.feedback).toBe("Fix heading");
  });

  it("regenerateChangeset returns new changeset", async () => {
    const cs = await regenerateChangeset("cs-123");
    expect(cs.id).toBe("cs-regenerated");
  });

  it("updateChangeContent completes", async () => {
    await expect(
      updateChangeContent("cs-123", "change-1", "# Updated"),
    ).resolves.toBeUndefined();
  });
});
