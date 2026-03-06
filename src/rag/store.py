import logging

import lancedb
import pyarrow as pa
from lancedb.rerankers import RRFReranker

logger = logging.getLogger("vault-agent")

_RRF_RERANKER = RRFReranker()

VECTOR_DIM = 512
TABLE_NAME = "vault_chunks"

SCHEMA = pa.schema(
    [
        pa.field("note_path", pa.utf8()),
        pa.field("heading", pa.utf8()),
        pa.field("content", pa.utf8()),
        pa.field("content_hash", pa.utf8()),
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
    ]
)


def get_db(lancedb_path: str) -> lancedb.DBConnection:
    return lancedb.connect(lancedb_path)


def get_or_create_table(db: lancedb.DBConnection) -> lancedb.table.Table:
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)


def get_existing_data(
    table: lancedb.table.Table,
) -> tuple[dict[str, str], object]:
    """Load table once, return hash map and DataFrame for reuse."""
    df = table.to_pandas()[["note_path", "heading", "content_hash"]]
    keys = df["note_path"] + "::" + df["heading"]
    hashes = dict(zip(keys, df["content_hash"]))
    return hashes, df


def upsert_chunks(table: lancedb.table.Table, rows: list[dict]) -> None:
    if not rows:
        return
    table.merge_insert(
        ["note_path", "heading"]
    ).when_matched_update_all().when_not_matched_insert_all().execute(rows)


def build_fts_index(table: lancedb.table.Table) -> None:
    table.create_fts_index("content", replace=True)


def delete_stale_chunks(
    table: lancedb.table.Table, valid_keys: set[str], existing_df=None
) -> int:
    df = (
        existing_df
        if existing_df is not None
        else table.to_pandas()[["note_path", "heading"]]
    )
    keys = df["note_path"] + "::" + df["heading"]
    stale_mask = ~keys.isin(valid_keys)
    stale_df = df[stale_mask]
    if stale_df.empty:
        return 0

    for _, row in stale_df.iterrows():
        path = row["note_path"].replace("'", "''")
        heading = row["heading"].replace("'", "''")
        table.delete(f"note_path = '{path}' AND heading = '{heading}'")

    return len(stale_df)


def search_vectors(
    table: lancedb.table.Table, query_vector: list[float], n: int = 10
) -> list[dict]:
    df = table.search(query_vector).limit(n).to_pandas()
    return [
        {
            "note_path": r["note_path"],
            "heading": r["heading"],
            "content": r["content"],
            "score": float(r["_distance"]),
            "search_type": "vector",
        }
        for r in df.to_dict(orient="records")
    ]


def search_hybrid(
    table: lancedb.table.Table,
    query_vector: list[float],
    query_text: str,
    n: int = 10,
) -> list[dict]:
    try:
        df = (
            table.search(query_type="hybrid")
            .vector(query_vector)
            .text(query_text)
            .rerank(_RRF_RERANKER)
            .limit(n)
            .to_pandas()
        )
        return [
            {
                "note_path": r["note_path"],
                "heading": r["heading"],
                "content": r["content"],
                "score": float(r["_relevance_score"]),
                "search_type": "hybrid",
            }
            for r in df.to_dict(orient="records")
        ]
    except Exception as e:
        logger.warning(f"Hybrid search failed, falling back to vector: {e}")
        return search_vectors(table, query_vector, n)
