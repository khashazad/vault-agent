from typing import Any, Literal

from pydantic import BaseModel, model_serializer

SearchType = Literal["hybrid", "vector"]


class HighlightInput(BaseModel):
    text: str
    source: str
    annotation: str | None = None


class BatchHighlightInput(BaseModel):
    highlights: list[HighlightInput]


class VaultNoteSummary(BaseModel):
    path: str
    title: str
    wikilinks: list[str]
    headings: list[str]


class VaultNote(BaseModel):
    path: str
    frontmatter: dict
    content: str
    wikilinks: list[str]


class VaultMap(BaseModel):
    total_notes: int
    notes: list[VaultNoteSummary]
    as_string: str


class ReadNoteInput(BaseModel):
    path: str


class CreateNoteInput(BaseModel):
    path: str
    content: str


class UpdateNoteInput(BaseModel):
    path: str
    operation: Literal["append_section"]
    heading: str | None = None
    content: str | None = None


class RoutingInfo(BaseModel):
    action: Literal["update", "create", "skip"]
    target_path: str | None = None
    reasoning: str
    confidence: float
    search_results_used: int = 0
    additional_targets: list[str] | None = None
    duplicate_notes: list[str] | None = None


class ProposedChange(BaseModel):
    id: str
    tool_name: Literal["create_note", "update_note"]
    input: dict[str, Any]
    original_content: str | None = None
    proposed_content: str
    diff: str
    status: Literal["pending", "approved", "rejected", "applied"] = "pending"


class Changeset(BaseModel):
    id: str
    highlights: list[HighlightInput]
    changes: list[ProposedChange]
    reasoning: str
    status: Literal[
        "pending", "applied", "rejected", "partially_applied", "skipped"
    ] = "pending"
    created_at: str
    routing: RoutingInfo | None = None
    feedback: str | None = None
    parent_changeset_id: str | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        d = handler(self)
        # Backward compat: include singular "highlight" pointing to first
        d["highlight"] = d["highlights"][0] if d["highlights"] else None
        return d


class RegenerateRequest(BaseModel):
    feedback: str


class ChunkInfo(BaseModel):
    note_path: str
    heading: str
    content: str
    score: float
    search_type: SearchType = "hybrid"


class IndexResponse(BaseModel):
    success: bool
    total_notes_scanned: int
    total_chunks: int
    chunks_added: int
    chunks_updated: int
    chunks_unchanged: int
    chunks_deleted: int
    duration_seconds: float


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkInfo]
    count: int
    embedding_model: str
    vector_dimensions: int
    search_type: SearchType = "hybrid"


class ChangeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]


class ApplyRequest(BaseModel):
    change_ids: list[str] | None = None


class ZoteroSyncRequest(BaseModel):
    collection_key: str | None = None
    paper_keys: list[str] | None = None
    full_sync: bool = False


class ZoteroSyncResponse(BaseModel):
    papers_found: int
    papers_processed: int
    changeset_ids: list[str]
    skipped_papers: list[str]
    library_version: int


class ZoteroPaperSummary(BaseModel):
    key: str
    title: str
    authors: list[str]
    year: str
    item_type: str
    last_synced: str | None = None
    changeset_id: str | None = None


class ZoteroPapersResponse(BaseModel):
    papers: list[ZoteroPaperSummary]
    total: int
    cache_updated_at: str | None = None


class ZoteroAnnotationItem(BaseModel):
    key: str
    text: str
    comment: str
    color: str
    page_label: str
    annotation_type: str
    date_added: str


class ZoteroPaperAnnotationsResponse(BaseModel):
    paper_key: str
    paper_title: str
    annotations: list[ZoteroAnnotationItem]
    total: int


class ZoteroPaperSyncRequest(BaseModel):
    paper_key: str
    excluded_annotation_keys: list[str] | None = None


class ZoteroCollection(BaseModel):
    key: str
    name: str
    parent_collection: str | None
    num_items: int
    num_collections: int


class ZoteroCollectionsResponse(BaseModel):
    collections: list[ZoteroCollection]
    total: int
