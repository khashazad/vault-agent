from typing import Literal

from pydantic import BaseModel, Field

SearchType = Literal["hybrid", "vector"]


class ChunkInfo(BaseModel):
    note_path: str = Field(description="Vault-relative path of the note")
    heading: str = Field(description="Section heading this chunk belongs to")
    content: str = Field(description="Text content of the chunk")
    score: float = Field(description="Relevance score from search ranking")
    search_type: SearchType = Field(
        default="hybrid", description="Search method that produced this result"
    )


class IndexResponse(BaseModel):
    success: bool = Field(description="Whether indexing completed successfully")
    total_notes_scanned: int = Field(description="Number of notes scanned in the vault")
    total_chunks: int = Field(description="Total chunks in the index after update")
    chunks_added: int = Field(description="New chunks added in this run")
    chunks_updated: int = Field(description="Existing chunks re-embedded")
    chunks_unchanged: int = Field(description="Chunks that did not need updating")
    chunks_deleted: int = Field(description="Stale chunks removed from the index")
    duration_seconds: float = Field(description="Wall-clock time for the indexing run")


class SearchResponse(BaseModel):
    query: str = Field(description="The original search query")
    results: list[ChunkInfo] = Field(description="Ranked search results")
    count: int = Field(description="Number of results returned")
    embedding_model: str = Field(description="Voyage AI model used for embeddings")
    vector_dimensions: int = Field(
        description="Dimensionality of the embedding vectors"
    )
    search_type: SearchType = Field(
        default="hybrid",
        description="Search method used (hybrid or vector-only fallback)",
    )
