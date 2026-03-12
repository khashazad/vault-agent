from pydantic import BaseModel, Field


class ZoteroSyncRequest(BaseModel):
    collection_key: str | None = Field(
        default=None, max_length=200, description="Zotero collection key to sync"
    )
    paper_keys: list[str] | None = Field(
        default=None, max_length=100, description="Specific paper keys to sync"
    )
    full_sync: bool = Field(
        default=False,
        description="Re-sync all papers regardless of previous sync state",
    )
    model: str = Field(
        default="haiku",
        pattern="^(haiku|sonnet)$",
        description="LLM model to use: haiku or sonnet",
    )


class ZoteroSyncResponse(BaseModel):
    papers_found: int = Field(
        description="Total papers found in the library or collection"
    )
    papers_processed: int = Field(
        description="Papers that were processed through the agent"
    )
    changeset_ids: list[str] = Field(
        description="IDs of changesets created during sync"
    )
    skipped_papers: list[str] = Field(
        description="Keys of papers skipped (no annotations or already synced)"
    )
    library_version: int = Field(description="Zotero library version after sync")


class ZoteroPaperSummary(BaseModel):
    key: str = Field(description="Zotero item key")
    title: str = Field(description="Paper title")
    authors: list[str] = Field(description="List of author names")
    year: str = Field(description="Publication year")
    item_type: str = Field(description="Zotero item type (e.g. journalArticle)")
    last_synced: str | None = Field(
        default=None, description="ISO 8601 timestamp of last sync"
    )
    changeset_id: str | None = Field(
        default=None, description="ID of the most recent changeset from sync"
    )
    annotation_count: int | None = Field(
        default=None, description="Number of annotations on this paper"
    )


class ZoteroPapersResponse(BaseModel):
    papers: list[ZoteroPaperSummary] = Field(description="Paginated list of papers")
    total: int = Field(description="Total number of papers matching the query")
    cache_updated_at: str | None = Field(
        default=None, description="When the paper cache was last refreshed"
    )


class ZoteroAnnotationItem(BaseModel):
    key: str = Field(description="Zotero annotation key")
    text: str = Field(description="Highlighted text content")
    comment: str = Field(description="User comment on the annotation")
    color: str = Field(description="Highlight color code")
    page_label: str = Field(description="Page label where the annotation appears")
    annotation_type: str = Field(description="Annotation type (e.g. highlight, note)")
    date_added: str = Field(
        description="ISO 8601 timestamp when annotation was created"
    )


class ZoteroPaperAnnotationsResponse(BaseModel):
    paper_key: str = Field(description="Zotero item key of the paper")
    paper_title: str = Field(description="Title of the paper")
    annotations: list[ZoteroAnnotationItem] = Field(
        description="All annotations on this paper"
    )
    total: int = Field(description="Total number of annotations")


class ZoteroPaperSyncRequest(BaseModel):
    paper_key: str = Field(
        max_length=200, description="Zotero item key of the paper to sync"
    )
    excluded_annotation_keys: list[str] | None = Field(
        default=None,
        max_length=500,
        description="Annotation keys to exclude from processing",
    )
    batch: bool = Field(
        default=False,
        description="Submit via Batch API for 50% cost reduction (async, poll for result)",
    )
    model: str = Field(
        default="haiku",
        pattern="^(haiku|sonnet)$",
        description="LLM model to use: haiku or sonnet",
    )


class ZoteroCollection(BaseModel):
    key: str = Field(description="Zotero collection key")
    name: str = Field(description="Collection name")
    parent_collection: str | None = Field(
        default=None, description="Key of the parent collection, if nested"
    )
    num_items: int = Field(description="Number of items in the collection")
    num_collections: int = Field(description="Number of sub-collections")


class ZoteroCollectionsResponse(BaseModel):
    collections: list[ZoteroCollection] = Field(
        description="List of Zotero collections"
    )
    total: int = Field(description="Total number of collections")


class PaperCacheStatusResponse(BaseModel):
    cached_count: int = Field(description="Number of papers in the local cache")
    cache_updated_at: str | None = Field(
        default=None, description="When the cache was last refreshed"
    )
    sync_in_progress: bool = Field(
        description="Whether a background sync is currently running"
    )


class RefreshResponse(BaseModel):
    status: str = Field(description="Result status (e.g. sync_triggered)")


class ZoteroStatusResponse(BaseModel):
    configured: bool = Field(description="Whether Zotero API credentials are set")
    last_version: int | None = Field(
        default=None, description="Last synced Zotero library version number"
    )
    last_synced: str | None = Field(
        default=None, description="ISO 8601 timestamp of last successful sync"
    )


class BatchJobStatusResponse(BaseModel):
    paper_key: str = Field(description="Zotero paper key")
    batch_id: str = Field(description="Anthropic Batch API batch ID")
    status: str = Field(
        description="Job status: pending, processing, completed, failed"
    )
    changeset_id: str | None = Field(
        default=None, description="Changeset ID once batch completes"
    )
    created_at: str = Field(description="ISO 8601 timestamp of job creation")
