from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["web", "zotero", "book"]


class SourceMetadata(BaseModel):
    title: str | None = None
    # zotero
    doi: str | None = None
    authors: list[str] | None = None
    year: str | None = None
    publication_title: str | None = None
    abstract: str | None = None
    paper_key: str | None = None
    # book (future)
    isbn: str | None = None
    chapter: str | None = None
    page_range: str | None = None
    # web
    url: str | None = None
    site_name: str | None = None


class ContentItem(BaseModel):
    text: str = Field(max_length=50_000)
    source: str = Field(max_length=2_000)
    annotation: str | None = Field(default=None, max_length=10_000)
    source_type: SourceType = "web"
    source_metadata: SourceMetadata | None = None


class BatchContentInput(BaseModel):
    items: list[ContentItem] = Field(max_length=50)
