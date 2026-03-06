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
    action: Literal["update", "create"]
    target_path: str | None = None
    reasoning: str
    confidence: float
    search_results_used: int = 0
    additional_targets: list[str] | None = None


class ProposedChange(BaseModel):
    id: str
    tool_name: Literal["create_note", "update_note"]
    input: dict[str, Any]
    original_content: str | None = None
    proposed_content: str
    diff: str
    status: Literal["pending", "approved", "rejected"] = "pending"


class Changeset(BaseModel):
    id: str
    highlights: list[HighlightInput]
    changes: list[ProposedChange]
    reasoning: str
    status: Literal["pending", "applied", "rejected", "partially_applied"] = "pending"
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
