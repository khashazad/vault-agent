from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["web", "zotero", "book", "clawdy"]


class SourceMetadata(BaseModel):
    title: str | None = Field(default=None, description="Title of the source document")
    # zotero
    doi: str | None = Field(default=None, description="Digital Object Identifier")
    authors: list[str] | None = Field(default=None, description="List of author names")
    year: str | None = Field(default=None, description="Publication year")
    publication_title: str | None = Field(
        default=None, description="Journal or publication name"
    )
    abstract: str | None = Field(default=None, description="Paper abstract")
    paper_key: str | None = Field(default=None, description="Zotero item key")
    # book (future)
    isbn: str | None = Field(default=None, description="ISBN for book sources")
    chapter: str | None = Field(default=None, description="Book chapter name")
    page_range: str | None = Field(
        default=None, description="Page range within the source"
    )
    # web
    url: str | None = Field(default=None, description="Source URL for web content")
    site_name: str | None = Field(default=None, description="Website or publisher name")


class ContentItem(BaseModel):
    text: str = Field(
        max_length=50_000, description="The highlighted or extracted text"
    )
    source: str = Field(
        max_length=2_000, description="URL or document title of the source"
    )
    annotation: str | None = Field(
        default=None, max_length=10_000, description="Optional user note or comment"
    )
    source_type: SourceType = Field(
        default="web", description="Origin type: web, zotero, or book"
    )
    color: str | None = Field(
        default=None, max_length=20, description="Annotation color hex code"
    )
    source_metadata: SourceMetadata | None = Field(
        default=None, description="Structured metadata about the source document"
    )
