from typing import Literal

from pydantic import BaseModel, Field

from .changesets import TokenUsage


class TagNode(BaseModel):
    name: str = Field(description="Tag name, e.g. 'machine-learning'")
    children: list["TagNode"] = Field(default_factory=list)
    description: str | None = None


class LinkTarget(BaseModel):
    title: str = Field(description="Canonical note title")
    aliases: list[str] = Field(
        default_factory=list, description="Alternate names LLM should recognize"
    )
    folder: str = Field(description="Target folder path")


class TaxonomyProposal(BaseModel):
    id: str
    folders: list[str]
    tag_hierarchy: list[TagNode]
    link_targets: list[LinkTarget]
    reasoning: str | None = None
    status: Literal["imported", "curated", "active"] = "imported"
    created_at: str


MigrationNoteStatus = Literal[
    "pending",
    "processing",
    "proposed",
    "approved",
    "rejected",
    "applied",
    "failed",
    "skipped",
]


class MigrationNote(BaseModel):
    id: str
    source_path: str
    target_path: str
    original_content: str
    proposed_content: str | None = None
    diff: str | None = None
    status: MigrationNoteStatus = "pending"
    error: str | None = None
    usage: TokenUsage | None = None


MigrationJobStatus = Literal[
    "pending",
    "migrating",
    "review",
    "applying",
    "completed",
    "failed",
    "cancelled",
]


class MigrationJob(BaseModel):
    id: str
    source_vault: str
    target_vault: str
    taxonomy_id: str | None = None
    status: MigrationJobStatus = "pending"
    total_notes: int
    processed_notes: int = 0
    total_usage: TokenUsage | None = None
    estimated_cost_usd: float | None = None
    created_at: str


class CostEstimate(BaseModel):
    total_notes: int
    total_chars: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    model: str
