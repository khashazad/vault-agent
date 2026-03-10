from typing import Any, Literal

from pydantic import BaseModel, model_validator

from .content import ContentItem, SourceType


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
    items: list[ContentItem]
    changes: list[ProposedChange]
    reasoning: str
    status: Literal[
        "pending", "applied", "rejected", "partially_applied", "skipped"
    ] = "pending"
    created_at: str
    source_type: SourceType = "web"
    routing: RoutingInfo | None = None
    feedback: str | None = None
    parent_changeset_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_highlights(cls, data):
        """Migrate old persisted changesets: highlights → items."""
        if not isinstance(data, dict):
            return data
        if "highlights" in data and "items" not in data:
            data["items"] = data.pop("highlights")
        data.setdefault("source_type", "web")
        return data


class ChangeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]


class ApplyRequest(BaseModel):
    change_ids: list[str] | None = None
