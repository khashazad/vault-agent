from dataclasses import dataclass
from typing import Literal

from src.rag.embedder import embed_query
from src.rag.store import get_db, get_or_create_table, search_hybrid


@dataclass
class SearchResult:
    note_path: str
    heading: str
    content: str
    score: float
    search_type: Literal["hybrid", "vector"] = "hybrid"


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
