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


# Connect to a LanceDB database at the given path.
#
# Args:
#     lancedb_path: Filesystem path for the LanceDB directory.
#
# Returns:
#     Open LanceDB connection.
def get_db(lancedb_path: str) -> lancedb.DBConnection:
    return lancedb.connect(lancedb_path)


# Open the vault_chunks table if it exists, otherwise create it with the defined schema.
#
# Args:
#     db: LanceDB connection.
#
# Returns:
#     The vault_chunks LanceDB table.
def get_or_create_table(db: lancedb.DBConnection) -> lancedb.table.Table:
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=SCHEMA)


# Load existing chunk data from the table for incremental indexing.
#
# Args:
#     table: LanceDB vault_chunks table.
#
# Returns:
#     Tuple of (content hash map keyed by "note_path::heading", DataFrame for reuse).
def get_existing_data(
    table: lancedb.table.Table,
) -> tuple[dict[str, str], object]:
    df = table.to_pandas()[["note_path", "heading", "content_hash"]]
    keys = df["note_path"] + "::" + df["heading"]
    hashes = dict(zip(keys, df["content_hash"]))
    return hashes, df


# Merge-insert chunk rows into the table, updating matched rows and inserting new ones.
#
# Args:
#     table: LanceDB vault_chunks table.
#     rows: List of chunk dicts with note_path, heading, content, content_hash, vector.
def upsert_chunks(table: lancedb.table.Table, rows: list[dict]) -> None:
    if not rows:
        return
    table.merge_insert(
        ["note_path", "heading"]
    ).when_matched_update_all().when_not_matched_insert_all().execute(rows)


# Rebuild the full-text search index on the content column.
def build_fts_index(table: lancedb.table.Table) -> None:
    table.create_fts_index("content", replace=True)


# Remove chunks whose "note_path::heading" key is not in valid_keys.
#
# Overwrites the table with only valid rows to avoid SQL filter injection.
#
# Args:
#     table: LanceDB vault_chunks table.
#     valid_keys: Set of "note_path::heading" keys to keep.
#     db: LanceDB connection (used to drop and recreate table).
#     existing_df: Optional pre-loaded DataFrame to avoid re-reading the table.
#
# Returns:
#     Number of stale chunks deleted.
def delete_stale_chunks(
    table: lancedb.table.Table,
    valid_keys: set[str],
    db: lancedb.DBConnection,
    existing_df=None,
) -> int:
    df = (
        existing_df
        if existing_df is not None
        else table.to_pandas()[["note_path", "heading"]]
    )
    keys = df["note_path"] + "::" + df["heading"]
    stale_mask = ~keys.isin(valid_keys)
    stale_count = int(stale_mask.sum())
    if stale_count == 0:
        return 0

    # Safe deletion: overwrite table with valid-only rows to avoid SQL filter injection
    full_df = table.to_pandas()
    full_keys = full_df["note_path"] + "::" + full_df["heading"]
    valid_df = full_df[full_keys.isin(valid_keys)]

    db.drop_table(TABLE_NAME)
    db.create_table(TABLE_NAME, data=valid_df, schema=SCHEMA)

    return stale_count


# Convert a search result DataFrame to a list of result dicts.
def _to_result_dicts(df, score_key: str, search_type: str) -> list[dict]:
    return [
        {
            "note_path": r["note_path"],
            "heading": r["heading"],
            "content": r["content"],
            "score": float(r[score_key]),
            "search_type": search_type,
        }
        for r in df.to_dict(orient="records")
    ]


# Search for similar chunks using vector distance only.
#
# Args:
#     table: LanceDB vault_chunks table.
#     query_vector: Embedding vector for the search query.
#     n: Maximum number of results to return.
#
# Returns:
#     List of result dicts with note_path, heading, content, score, search_type.
def search_vectors(
    table: lancedb.table.Table, query_vector: list[float], n: int = 10
) -> list[dict]:
    df = table.search(query_vector).limit(n).to_pandas()
    return _to_result_dicts(df, "_distance", "vector")


# Hybrid vector + full-text search with RRF reranking.
#
# Falls back to vector-only search if hybrid fails.
#
# Args:
#     table: LanceDB vault_chunks table.
#     query_vector: Embedding vector for the search query.
#     query_text: Raw text query for full-text search.
#     n: Maximum number of results to return.
#
# Returns:
#     List of result dicts with note_path, heading, content, score, search_type.
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
        return _to_result_dicts(df, "_relevance_score", "hybrid")
    except Exception as e:
        logger.warning("Hybrid search failed, falling back to vector: %s", e)
        return search_vectors(table, query_vector, n)
