import type {
  Changeset,
  ProposedChange,
  ContentItem,
  ZoteroPaperSummary,
  ZoteroAnnotationItem,
  ZoteroCollection,
} from "../types";

export function makeContentItem(overrides?: Partial<ContentItem>): ContentItem {
  return {
    text: "Neural networks are universal approximators.",
    source: "https://example.com/article",
    source_type: "web",
    ...overrides,
  };
}

export function makeProposedChange(overrides?: Partial<ProposedChange>): ProposedChange {
  return {
    id: "change-1",
    tool_name: "create_note",
    input: { path: "Papers/Test.md", content: "# Test" },
    original_content: null,
    proposed_content: "# Test\n\nContent.",
    diff: "--- a/Papers/Test.md\n+++ b/Papers/Test.md\n@@ -0,0 +1,3 @@\n+# Test\n+\n+Content.\n",
    status: "pending",
    ...overrides,
  };
}

export function makeChangeset(overrides?: Partial<Changeset>): Changeset {
  return {
    id: "cs-test-1",
    items: [makeContentItem()],
    changes: [makeProposedChange()],
    reasoning: "Created a new note.",
    status: "pending",
    created_at: "2024-01-01T00:00:00Z",
    source_type: "web",
    routing: {
      action: "create",
      target_path: "Papers/Test.md",
      reasoning: "New topic.",
      confidence: 0.9,
      search_results_used: 3,
      additional_targets: null,
      duplicate_notes: null,
    },
    usage: null,
    feedback: null,
    parent_changeset_id: null,
    ...overrides,
  };
}

export function makePaper(overrides?: Partial<ZoteroPaperSummary>): ZoteroPaperSummary {
  return {
    key: "PAPER1",
    title: "Test Paper Title",
    authors: ["Smith, John", "Doe, Jane"],
    year: "2024",
    item_type: "journalArticle",
    last_synced: null,
    changeset_id: null,
    annotation_count: 5,
    ...overrides,
  };
}

export function makeAnnotation(overrides?: Partial<ZoteroAnnotationItem>): ZoteroAnnotationItem {
  return {
    key: "ANN1",
    text: "Important finding about neural networks.",
    comment: "Key result",
    color: "#ffd400",
    page_label: "42",
    annotation_type: "highlight",
    date_added: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCollection(overrides?: Partial<ZoteroCollection>): ZoteroCollection {
  return {
    key: "COL1",
    name: "My Collection",
    parent_collection: null,
    num_items: 5,
    num_collections: 0,
    ...overrides,
  };
}
