from typing import Any, Literal

from pydantic import BaseModel


class HighlightInput(BaseModel):
    text: str
    source: str
    annotation: str | None = None
    tags: list[str] | None = None


class VaultNoteSummary(BaseModel):
    path: str
    title: str
    tags: list[str]
    wikilinks: list[str]
    headings: list[str]


class VaultNote(BaseModel):
    path: str
    frontmatter: dict
    content: str
    wikilinks: list[str]
    tags: list[str]


class VaultMap(BaseModel):
    total_notes: int
    notes: list[VaultNoteSummary]
    as_string: str


class ProcessResult(BaseModel):
    success: bool
    action: str
    affected_notes: list[str]
    reasoning: str


class ReadNoteInput(BaseModel):
    path: str


class CreateNoteInput(BaseModel):
    path: str
    content: str


class UpdateNoteInput(BaseModel):
    path: str
    operation: Literal["append_section", "add_tags"]
    heading: str | None = None
    content: str | None = None
    tags: list[str] | None = None


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
    highlight: HighlightInput
    changes: list[ProposedChange]
    reasoning: str
    status: Literal["pending", "applied", "rejected", "partially_applied"] = "pending"
    created_at: str


class AgentStreamEvent(BaseModel):
    type: Literal[
        "reasoning", "tool_call", "tool_result", "proposed_change", "complete", "error"
    ]
    data: dict[str, Any]


class ChunkInfo(BaseModel):
    note_path: str
    heading: str
    content: str
    score: float


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
