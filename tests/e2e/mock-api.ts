import type { Page } from "@playwright/test";

/** Canned API responses for E2E route interception */
const MOCK_CHANGESET_SUMMARIES = {
  changesets: [
    {
      id: "cshist01-abcd-1234",
      status: "applied",
      created_at: "2025-01-15T10:30:00Z",
      source_type: "zotero",
      change_count: 1,
      routing: {
        action: "create",
        target_path: "Papers/Attention.md",
        reasoning: "New paper note",
        confidence: 0.95,
        additional_targets: null,
        duplicate_notes: null,
      },
      feedback: null,
      parent_changeset_id: null,
    },
    {
      id: "cshist02-efgh-5678",
      status: "pending",
      created_at: "2025-01-14T08:00:00Z",
      source_type: "web",
      change_count: 2,
      routing: {
        action: "update",
        target_path: "Notes/ML.md",
        reasoning: "Appending to existing note",
        confidence: 0.8,
        additional_targets: null,
        duplicate_notes: null,
      },
      feedback: null,
      parent_changeset_id: null,
    },
  ],
  total: 2,
};

const MOCK_RESPONSES: Record<string, unknown> = {
  "/health": { status: "ok", vault_path: "/mock/vault" },
  "/zotero/status": {
    configured: true,
    last_version: 42,
    last_synced: "2025-01-15T10:00:00Z",
  },
  "/zotero/collections": {
    collections: [
      {
        key: "COL1",
        name: "Machine Learning",
        parent_collection: null,
        num_items: 12,
        num_collections: 1,
      },
      {
        key: "COL2",
        name: "Deep Learning",
        parent_collection: "COL1",
        num_items: 5,
        num_collections: 0,
      },
    ],
    total: 2,
  },
  "/zotero/papers/cache-status": {
    cached_count: 3,
    cache_updated_at: "2025-01-15T10:00:00Z",
    sync_in_progress: false,
  },
};

const MOCK_PAPERS = {
  papers: [
    {
      key: "P1",
      title: "Attention Is All You Need",
      authors: ["Vaswani, A.", "Shazeer, N."],
      year: "2017",
      item_type: "journalArticle",
      last_synced: null,
      changeset_id: null,
      annotation_count: 5,
    },
    {
      key: "P2",
      title: "BERT: Pre-training of Deep Bidirectional Transformers",
      authors: ["Devlin, J."],
      year: "2019",
      item_type: "conferencePaper",
      last_synced: "2025-01-10T08:00:00Z",
      changeset_id: "cs-old",
      annotation_count: 3,
    },
    {
      key: "P3",
      title: "GPT-4 Technical Report",
      authors: ["OpenAI"],
      year: "2023",
      item_type: "report",
      last_synced: null,
      changeset_id: null,
      annotation_count: 8,
    },
  ],
  total: 3,
  cache_updated_at: "2025-01-15T10:00:00Z",
};

const MOCK_ANNOTATIONS = {
  paper_key: "P1",
  paper_title: "Attention Is All You Need",
  annotations: [
    {
      key: "A1",
      text: "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
      comment: "Key background claim",
      color: "#ffd400",
      page_label: "1",
      annotation_type: "highlight",
      date_added: "2025-01-12T09:00:00Z",
    },
    {
      key: "A2",
      text: "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
      comment: "",
      color: "#5fb236",
      page_label: "1",
      annotation_type: "highlight",
      date_added: "2025-01-12T09:05:00Z",
    },
  ],
  total: 2,
};

const MOCK_CHANGESET = {
  id: "cs-e2e-1",
  items: [
    {
      text: "The Transformer architecture",
      source: "Attention Is All You Need",
      source_type: "zotero",
    },
  ],
  changes: [
    {
      id: "ch-1",
      tool_name: "create_note",
      input: { path: "Papers/Attention Is All You Need.md" },
      original_content: null,
      proposed_content:
        "---\ntags: [ml, transformers]\ncreated: 2025-01-15\n---\n\n# Attention Is All You Need\n\n## Key Highlights\n\n> The dominant sequence transduction models...\n",
      diff: "@@ -0,0 +1,8 @@\n+---\n+tags: [ml, transformers]\n+created: 2025-01-15\n+---\n+\n+# Attention Is All You Need\n+\n+## Key Highlights\n",
      status: "pending",
    },
  ],
  reasoning: "Created new note for paper not yet in vault",
  status: "pending",
  created_at: "2025-01-15T10:30:00Z",
  source_type: "zotero",
  routing: {
    action: "create",
    target_path: "Papers/Attention Is All You Need.md",
    reasoning: "No existing note found for this paper",
    confidence: 0.95,
    additional_targets: null,
    duplicate_notes: null,
  },
  feedback: null,
  parent_changeset_id: null,
};

/**
 * Set up Playwright route interception for all API endpoints.
 * Call this in beforeEach to mock the backend.
 */
export async function mockApi(page: Page) {
  // Static endpoints
  for (const [path, body] of Object.entries(MOCK_RESPONSES)) {
    await page.route(`**${path}`, (route) =>
      route.fulfill({ json: body })
    );
  }

  // Papers (supports query params)
  await page.route("**/zotero/papers?*", (route) =>
    route.fulfill({ json: MOCK_PAPERS })
  );
  // Papers without query string (fallback)
  await page.route("**/zotero/papers", (route) => {
    if (route.request().url().includes("?")) return route.fallback();
    return route.fulfill({ json: MOCK_PAPERS });
  });

  // Paper annotations
  await page.route("**/zotero/papers/*/annotations", (route) =>
    route.fulfill({ json: MOCK_ANNOTATIONS })
  );

  // Paper sync (POST)
  await page.route("**/zotero/papers/*/sync", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ json: MOCK_CHANGESET });
    }
    return route.fallback();
  });

  // Refresh (POST)
  await page.route("**/zotero/papers/refresh", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });

  // Changeset list
  await page.route("**/changesets?*", (route) =>
    route.fulfill({ json: MOCK_CHANGESET_SUMMARIES })
  );
  await page.route("**/changesets", (route) => {
    if (route.request().url().includes("?")) return route.fallback();
    // Bare /changesets with no query string (list all)
    if (route.request().method() === "GET" && !route.request().url().includes("/changesets/")) {
      return route.fulfill({ json: MOCK_CHANGESET_SUMMARIES });
    }
    return route.fallback();
  });

  // Request changes
  await page.route("**/changesets/*/request-changes", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        json: { id: "cshist02-efgh-5678", status: "revision_requested", feedback: "Fix heading" },
      });
    }
    return route.fallback();
  });

  // Regenerate
  await page.route("**/changesets/*/regenerate", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ json: MOCK_CHANGESET });
    }
    return route.fallback();
  });

  // Changeset operations
  await page.route("**/changesets/*/apply", (route) =>
    route.fulfill({
      json: { applied: ["ch-1"], failed: [] },
    })
  );
  await page.route("**/changesets/*/reject", (route) =>
    route.fulfill({ status: 204 })
  );
  await page.route("**/changesets/*/changes/*", (route) =>
    route.fulfill({ status: 204 })
  );
  await page.route("**/changesets/*", (route) => {
    if (route.request().method() === "DELETE") {
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ json: MOCK_CHANGESET });
  });
}
