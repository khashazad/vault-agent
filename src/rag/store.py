import lancedb
import pyarrow as pa

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
        "note_path", "heading"
    ).when_matched_update_all().when_not_matched_insert_all().execute(rows)


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
    stale_filters: list[str] = []
    for _, row in stale_df.iterrows():
        path_escaped = row["note_path"].replace("'", "\\'")
        heading_escaped = row["heading"].replace("'", "\\'")
        stale_filters.append(
            f"(note_path = '{path_escaped}' AND heading = '{heading_escaped}')"
        )

    if not stale_filters:
        return 0

    count = len(stale_filters)
    filter_expr = " OR ".join(stale_filters)
    table.delete(filter_expr)
    return count


def search_vectors(
    table: lancedb.table.Table, query_vector: list[float], n: int = 10
) -> list[dict]:
    results = table.search(query_vector).limit(n).to_pandas()
    rows: list[dict] = []
    for _, row in results.iterrows():
        rows.append(
            {
                "note_path": row["note_path"],
                "heading": row["heading"],
                "content": row["content"],
                "score": float(row["_distance"]),
            }
        )
    return rows
