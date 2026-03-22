import type {
  Changeset,
  ChangesetSummary,
  LinkTargetInfo,
  ProposedChange,
  ContentItem,
  PassageAnnotation,
  TagInfo,
  VaultTaxonomy,
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

export function makeProposedChange(
  overrides?: Partial<ProposedChange>,
): ProposedChange {
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
      additional_targets: null,
      duplicate_notes: null,
    },
    usage: null,
    feedback: null,
    parent_changeset_id: null,
    ...overrides,
  };
}

export function makeChangesetSummary(
  overrides?: Partial<ChangesetSummary>,
): ChangesetSummary {
  return {
    id: "cs-test-1",
    status: "pending",
    created_at: "2024-01-01T00:00:00Z",
    source_type: "web",
    change_count: 1,
    routing: {
      action: "create",
      target_path: "Papers/Test.md",
      reasoning: "New topic.",
      confidence: 0.9,
      additional_targets: null,
      duplicate_notes: null,
    },
    feedback: null,
    parent_changeset_id: null,
    ...overrides,
  };
}

export function makePaper(
  overrides?: Partial<ZoteroPaperSummary>,
): ZoteroPaperSummary {
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

export function makeAnnotation(
  overrides?: Partial<ZoteroAnnotationItem>,
): ZoteroAnnotationItem {
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

export function makePassageAnnotation(
  overrides?: Partial<PassageAnnotation>,
): PassageAnnotation {
  return {
    id: "ann-1",
    selectedText: "Neural networks are universal approximators.",
    comment: "Clarify which theorem this refers to",
    ...overrides,
  };
}

export function makeCollection(
  overrides?: Partial<ZoteroCollection>,
): ZoteroCollection {
  return {
    key: "COL1",
    name: "My Collection",
    parent_collection: null,
    num_items: 5,
    num_collections: 0,
    ...overrides,
  };
}

export function makeTagInfo(overrides?: Partial<TagInfo>): TagInfo {
  return { name: "research", count: 10, ...overrides };
}

export function makeLinkTargetInfo(
  overrides?: Partial<LinkTargetInfo>,
): LinkTargetInfo {
  return { title: "Machine Learning", count: 5, ...overrides };
}

export function makeVaultTaxonomy(
  overrides?: Partial<VaultTaxonomy>,
): VaultTaxonomy {
  return {
    folders: ["Papers", "Topics", "Projects", "daily"],
    tags: [
      makeTagInfo({ name: "research", count: 15 }),
      makeTagInfo({ name: "research/ai", count: 8 }),
      makeTagInfo({ name: "research/ml", count: 5 }),
      makeTagInfo({ name: "paper", count: 20 }),
      makeTagInfo({ name: "daily", count: 45 }),
    ],
    tag_hierarchy: [
      { name: "daily", children: [], description: null },
      { name: "paper", children: [], description: null },
      {
        name: "research",
        children: [
          { name: "ai", children: [], description: null },
          { name: "ml", children: [], description: null },
        ],
        description: null,
      },
    ],
    link_targets: [
      makeLinkTargetInfo({ title: "Machine Learning", count: 12 }),
      makeLinkTargetInfo({ title: "Projects/My Project", count: 3 }),
    ],
    total_notes: 142,
    ...overrides,
  };
}
