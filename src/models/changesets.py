from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

from .highlights import HighlightInput


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
    feedback: str = Field(max_length=10_000)


class ChangeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]


class ApplyRequest(BaseModel):
    change_ids: list[str] | None = None
