from dataclasses import dataclass

from src.rag.embedder import embed_query
from src.rag.store import get_db, get_or_create_table, search_vectors


@dataclass
class SearchResult:
    note_path: str
    heading: str
    content: str
    score: float


async def search_vault(
    query: str, voyage_api_key: str, lancedb_path: str, n: int = 10
) -> list[SearchResult]:
    query_vector = await embed_query(voyage_api_key, query)

    db = get_db(lancedb_path)
    table = get_or_create_table(db)
    raw_results = search_vectors(table, query_vector, n=n)

    return [
        SearchResult(
            note_path=r["note_path"],
            heading=r["heading"],
            content=r["content"],
            score=r["score"],
        )
        for r in raw_results
    ]
