from pydantic import BaseModel, Field


class ZoteroSyncRequest(BaseModel):
    collection_key: str | None = Field(default=None, max_length=200)
    paper_keys: list[str] | None = Field(default=None, max_length=100)
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
    paper_key: str = Field(max_length=200)
    excluded_annotation_keys: list[str] | None = Field(default=None, max_length=500)


class ZoteroCollection(BaseModel):
    key: str
    name: str
    parent_collection: str | None
    num_items: int
    num_collections: int


class ZoteroCollectionsResponse(BaseModel):
    collections: list[ZoteroCollection]
    total: int
