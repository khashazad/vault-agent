import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { makeChangeset, makePaper, makeAnnotation } from "./factories";

export const handlers = [
  // Health
  http.get("/health", () =>
    HttpResponse.json({
      status: "ok",
      vaultConfigured: true,
      timestamp: new Date().toISOString(),
    }),
  ),

  // Changesets
  http.get("/changesets/:id", ({ params }) =>
    HttpResponse.json(makeChangeset({ id: params.id as string })),
  ),

  http.patch(
    "/changesets/:changesetId/changes/:changeId",
    async ({ request }) => {
      const body = (await request.json()) as { status: string };
      return HttpResponse.json({ id: "change-1", status: body.status });
    },
  ),

  http.post("/changesets/:id/apply", () =>
    HttpResponse.json({ applied: ["change-1"], failed: [] }),
  ),

  http.post("/changesets/:id/reject", ({ params }) =>
    HttpResponse.json({ id: params.id, status: "rejected" }),
  ),

  // Zotero
  http.get("/zotero/status", () =>
    HttpResponse.json({
      configured: true,
      last_version: 100,
      last_synced: "2024-01-01T00:00:00Z",
    }),
  ),

  http.get("/zotero/papers", () =>
    HttpResponse.json({
      papers: [makePaper()],
      total: 1,
      cache_updated_at: "2024-01-01T00:00:00Z",
    }),
  ),

  http.get("/zotero/papers/cache-status", () =>
    HttpResponse.json({
      cached_count: 10,
      cache_updated_at: "2024-01-01T00:00:00Z",
      sync_in_progress: false,
    }),
  ),

  http.post("/zotero/papers/refresh", () =>
    HttpResponse.json({ status: "sync_triggered" }),
  ),

  http.get("/zotero/collections", () =>
    HttpResponse.json({
      collections: [
        {
          key: "COL1",
          name: "My Collection",
          parent_collection: null,
          num_items: 5,
          num_collections: 0,
        },
      ],
      total: 1,
    }),
  ),

  http.get("/zotero/papers/:key/annotations", ({ params }) =>
    HttpResponse.json({
      paper_key: params.key,
      paper_title: "Test Paper",
      annotations: [makeAnnotation()],
      total: 1,
    }),
  ),

  http.post("/zotero/papers/:key/sync", () =>
    HttpResponse.json(makeChangeset()),
  ),

  http.post("/zotero/sync", () =>
    HttpResponse.json({
      papers_found: 1,
      papers_processed: 1,
      changeset_ids: ["cs-1"],
      skipped_papers: [],
      library_version: 101,
    }),
  ),
];

export const server = setupServer(...handlers);
