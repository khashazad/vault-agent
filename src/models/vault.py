from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .migration import TagNode


class VaultNoteSummary(BaseModel):
    path: str = Field(description="Vault-relative file path")
    title: str = Field(description="Note title derived from filename or frontmatter")
    wikilinks: list[str] = Field(description="Wikilinks found in the note")
    headings: list[str] = Field(description="Markdown headings in the note")


class VaultNote(BaseModel):
    path: str = Field(description="Vault-relative file path")
    frontmatter: dict = Field(description="Parsed YAML frontmatter as key-value pairs")
    content: str = Field(description="Full note content including frontmatter")
    wikilinks: list[str] = Field(description="Wikilinks found in the note")


class VaultMap(BaseModel):
    total_notes: int = Field(description="Total number of notes in the vault")
    notes: list[VaultNoteSummary] = Field(description="Summary of each note")
    as_string: str = Field(
        description="Human-readable vault structure string for LLM context"
    )


class HealthResponse(BaseModel):
    status: str = Field(description="Server status (ok)")
    vaultConfigured: bool = Field(description="Whether a vault is configured")
    timestamp: str = Field(description="Current UTC timestamp in ISO 8601")


class VaultMapResponse(BaseModel):
    totalNotes: int = Field(description="Total number of notes in the vault")
    notes: list[VaultNoteSummary] = Field(description="Per-note summaries")


class VaultConfigResponse(BaseModel):
    vault_path: str | None = Field(description="Absolute path to the configured vault")
    vault_name: str | None = Field(description="Directory basename of the vault")


class VaultConfigRequest(BaseModel):
    vault_path: str = Field(description="Absolute path to an Obsidian vault")


class VaultPickerResponse(BaseModel):
    path: str | None = Field(description="Selected folder path, None if cancelled")
    cancelled: bool = Field(description="Whether the user cancelled the dialog")


class VaultHistoryEntry(BaseModel):
    path: str = Field(description="Absolute vault path")
    name: str = Field(description="Vault directory name")
    last_opened: str = Field(description="ISO 8601 timestamp of last connection")


class VaultHistoryResponse(BaseModel):
    vaults: list[VaultHistoryEntry] = Field(description="Previously opened vaults")


# Tag name with usage count across vault notes.
class TagInfo(BaseModel):
    name: str = Field(description="Full tag name e.g. 'research/ai'")
    count: int = Field(description="Number of notes using this tag")


# Wikilink target with usage count.
class LinkTargetInfo(BaseModel):
    title: str = Field(description="Wikilink target text")
    count: int = Field(description="Usage count across vault")


# Full vault taxonomy: folders, tags, link targets.
class VaultTaxonomy(BaseModel):
    folders: list[str] = Field(description="Unique folder paths, sorted")
    tags: list[TagInfo] = Field(description="Flat tag list with counts")
    tag_hierarchy: list[TagNode] = Field(
        description="Tags grouped into tree via slash separators"
    )
    link_targets: list[LinkTargetInfo] = Field(
        description="Wikilink targets with usage counts"
    )
    total_notes: int = Field(description="Total notes scanned")


# Single curation operation on a tag, folder, or link target.
class TaxonomyCurationOp(BaseModel):
    op: Literal[
        "rename_tag", "merge_tags", "delete_tag",
        "rename_folder", "move_folder", "delete_folder",
        "rename_link", "merge_links", "delete_link",
    ] = Field(description="Curation operation type")
    target: str = Field(description="Tag, folder, or link target to operate on")
    value: str | None = Field(
        default=None, description="New name (rename) or merge destination"
    )

    @model_validator(mode="after")
    def _validate_value_for_op(self) -> "TaxonomyCurationOp":
        delete_ops = {"delete_tag", "delete_folder", "delete_link"}
        if self.op in delete_ops and self.value is not None:
            raise ValueError(f"'value' must be None for {self.op}")
        if self.op not in delete_ops and not self.value:
            raise ValueError(f"'value' is required for {self.op}")
        return self


# Request body for taxonomy curation endpoint.
class TaxonomyCurationRequest(BaseModel):
    operations: list[TaxonomyCurationOp] = Field(
        description="List of curation operations to apply"
    )


# Response from taxonomy curation endpoint.
class TaxonomyCurationResponse(BaseModel):
    changeset_id: str = Field(description="ID of the generated changeset")
    change_count: int = Field(description="Number of notes affected")
