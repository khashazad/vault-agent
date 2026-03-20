from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .content import ContentItem, SourceType

# Valid changeset lifecycle statuses.
ChangesetStatus = Literal[
    "pending",
    "applied",
    "rejected",
    "partially_applied",
    "skipped",
    "revision_requested",
]


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    api_calls: int = 1
    tool_calls: int = 0
    is_batch: bool = False
    model: str = "haiku"
    total_cost_usd: float


class RoutingInfo(BaseModel):
    action: Literal["update", "create", "skip"] = Field(
        description="Whether to update existing note, create new, or skip"
    )
    target_path: str | None = Field(
        default=None, description="Vault-relative path of the target note"
    )
    reasoning: str = Field(description="Agent's explanation for the routing decision")
    confidence: float = Field(description="Confidence score 0-1")
    additional_targets: list[str] | None = Field(
        default=None, description="Extra note paths affected"
    )
    duplicate_notes: list[str] | None = Field(
        default=None, description="Paths of detected duplicate notes"
    )


class ProposedChange(BaseModel):
    id: str = Field(description="Unique change identifier")
    tool_name: Literal["create_note", "update_note"] = Field(
        description="Which write operation to perform"
    )
    input: dict[str, Any] = Field(description="Tool input parameters")
    original_content: str | None = Field(
        default=None,
        description="Current note content before change (null for new notes)",
    )
    proposed_content: str = Field(description="Full note content after change")
    diff: str = Field(description="Unified diff of the change")
    status: Literal["pending", "approved", "rejected", "applied"] = Field(
        default="pending", description="Current approval status"
    )


class Changeset(BaseModel):
    id: str = Field(description="Unique changeset identifier")
    items: list[ContentItem] = Field(
        description="Content items that produced this changeset"
    )
    changes: list[ProposedChange] = Field(description="Proposed vault changes")
    reasoning: str = Field(description="Agent's overall reasoning for the changes")
    status: ChangesetStatus = Field(
        default="pending", description="Current changeset status"
    )
    created_at: str = Field(description="ISO 8601 creation timestamp")
    source_type: SourceType = Field(
        default="web", description="Origin type of the content items"
    )
    routing: RoutingInfo | None = Field(
        default=None, description="Agent's routing decision for note placement"
    )
    usage: TokenUsage | None = Field(
        default=None, description="LLM token usage and cost"
    )
    feedback: str | None = Field(
        default=None, description="User feedback for regeneration"
    )
    parent_changeset_id: str | None = Field(
        default=None,
        description="ID of the parent changeset if this was regenerated",
    )

    # Migrate old persisted changesets: highlights -> items.
    @model_validator(mode="before")
    @classmethod
    def _migrate_highlights(cls, data):
        if not isinstance(data, dict):
            return data
        if "highlights" in data and "items" not in data:
            data["items"] = data.pop("highlights")
        data.setdefault("source_type", "web")
        return data


class ChangeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"] = Field(
        description="New status for the change"
    )


class ApplyRequest(BaseModel):
    change_ids: list[str] | None = Field(
        default=None,
        description="Specific change IDs to apply; if null, all approved changes are applied",
    )


class ChangeStatusResponse(BaseModel):
    id: str = Field(description="Change identifier")
    status: str = Field(description="Updated status")


class ApplyFailure(BaseModel):
    id: str = Field(description="ID of the change that failed to apply")
    error: str = Field(description="Error message describing the failure")


class ApplyResponse(BaseModel):
    applied: list[str] = Field(description="IDs of successfully applied changes")
    failed: list[ApplyFailure] = Field(
        description="Changes that failed to apply with error details"
    )


class RejectResponse(BaseModel):
    id: str = Field(description="Changeset identifier")
    status: str = Field(description="New status (rejected)")


class FeedbackRequest(BaseModel):
    feedback: str = Field(description="User feedback for regeneration")


class ChangeContentUpdate(BaseModel):
    status: Literal["approved", "rejected"] | None = None
    proposed_content: str | None = None


# Lightweight changeset for list view — no diffs/content.
class ChangesetSummary(BaseModel):
    id: str
    status: str
    created_at: str
    source_type: SourceType
    change_count: int
    routing: RoutingInfo | None
    feedback: str | None
    parent_changeset_id: str | None


class ChangesetListResponse(BaseModel):
    changesets: list[ChangesetSummary]
    total: int
