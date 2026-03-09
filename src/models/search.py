from typing import Literal

from pydantic import BaseModel

SearchType = Literal["hybrid", "vector"]


class ChunkInfo(BaseModel):
    note_path: str
    heading: str
    content: str
    score: float
    search_type: SearchType = "hybrid"


class IndexResponse(BaseModel):
    success: bool
    total_notes_scanned: int
    total_chunks: int
    chunks_added: int
    chunks_updated: int
    chunks_unchanged: int
    chunks_deleted: int
    duration_seconds: float


class SearchResponse(BaseModel):
    query: str
    results: list[ChunkInfo]
    count: int
    embedding_model: str
    vector_dimensions: int
    search_type: SearchType = "hybrid"
