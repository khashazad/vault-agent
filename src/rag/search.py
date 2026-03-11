from dataclasses import dataclass
from typing import Literal

from src.rag.embedder import embed_query
from src.rag.store import get_db, get_or_create_table, search_hybrid


# A single ranked result from vault search with content snippet and relevance score.
@dataclass
class SearchResult:
    note_path: str
    heading: str
    content: str
    score: float
    search_type: Literal["hybrid", "vector"] = "hybrid"


# Run hybrid semantic + full-text search over indexed vault chunks.
#
# Embeds the query via Voyage AI, then performs RRF-ranked hybrid search
# in LanceDB combining vector similarity and full-text matching.
#
# Args:
#     query: Natural language search query.
#     voyage_api_key: Voyage AI API key for embedding.
#     lancedb_path: Path to the LanceDB database directory.
#     n: Maximum number of results to return.
#
# Returns:
#     Ranked list of SearchResult objects.
async def search_vault(
    query: str, voyage_api_key: str, lancedb_path: str, n: int = 10
) -> list[SearchResult]:
    query_vector = await embed_query(voyage_api_key, query)

    db = get_db(lancedb_path)
    table = get_or_create_table(db)
    raw_results = search_hybrid(table, query_vector, query, n=n)

    return [
        SearchResult(
            note_path=r["note_path"],
            heading=r["heading"],
            content=r["content"],
            score=r["score"],
            search_type=r["search_type"],
        )
        for r in raw_results
    ]
