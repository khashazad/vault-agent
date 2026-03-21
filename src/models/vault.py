from pydantic import BaseModel, Field


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
