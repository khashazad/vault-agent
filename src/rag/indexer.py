import logging
import time
from dataclasses import dataclass
from pathlib import PurePosixPath

from src.rag.chunker import Chunk, chunk_note
from src.vault import iter_markdown_files
from src.vault.reader import parse_frontmatter
from src.rag.embedder import embed_texts
from src.rag.store import (
    get_db,
    get_or_create_table,
    get_existing_data,
    upsert_chunks,
    build_fts_index,
    delete_stale_chunks,
)

logger = logging.getLogger("vault-agent")


# Statistics from a vault indexing run.
@dataclass
class IndexStats:
    total_notes_scanned: int
    total_chunks: int
    chunks_added: int
    chunks_updated: int
    chunks_unchanged: int
    chunks_deleted: int
    duration_seconds: float


# Scan all markdown files in the vault and split them into heading-based chunks.
def _scan_and_chunk(vault_path: str) -> list[Chunk]:
    all_chunks: list[Chunk] = []

    for md_file, file_path in iter_markdown_files(vault_path):
        raw = md_file.read_text(encoding="utf-8")
        _, content = parse_frontmatter(raw)
        title = PurePosixPath(file_path).stem
        all_chunks.extend(chunk_note(file_path, title, content))

    return all_chunks


# Build the text string sent to Voyage AI for embedding, prefixed with note title and heading.
def _build_embed_text(chunk: Chunk) -> str:
    title = PurePosixPath(chunk.note_path).stem
    return f"Note: {title} > {chunk.heading}\n\n{chunk.content}"


# Incrementally index the vault into LanceDB: scan, chunk, embed changed chunks, upsert, and prune stale entries.
#
# Only re-embeds chunks whose content hash has changed since the last run.
# Rebuilds the FTS index after any mutations.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     voyage_api_key: Voyage AI API key for embedding.
#     lancedb_path: Path to the LanceDB database directory.
#
# Returns:
#     IndexStats with counts of added, updated, unchanged, and deleted chunks.
async def index_vault(
    vault_path: str, voyage_api_key: str, lancedb_path: str
) -> IndexStats:
    start = time.time()

    # Scan and chunk
    all_chunks = _scan_and_chunk(vault_path)
    note_paths = set(c.note_path for c in all_chunks)
    total_notes = len(note_paths)

    logger.info("Scanned %d notes, %d chunks", total_notes, len(all_chunks))

    # Compare with existing hashes
    db = get_db(lancedb_path)
    table = get_or_create_table(db)

    existing_hashes = {}
    existing_df = None
    try:
        if table.count_rows() > 0:
            existing_hashes, existing_df = get_existing_data(table)
    except Exception as e:
        logger.warning("Failed to load existing data from LanceDB: %s", e)

    changed_chunks: list[Chunk] = []
    unchanged_count = 0

    for chunk in all_chunks:
        key = f"{chunk.note_path}::{chunk.heading}"
        if key in existing_hashes and existing_hashes[key] == chunk.content_hash:
            unchanged_count += 1
        else:
            changed_chunks.append(chunk)

    logger.info("%d changed, %d unchanged", len(changed_chunks), unchanged_count)

    # Embed changed chunks
    added = 0
    updated = 0

    if changed_chunks:
        texts = [_build_embed_text(c) for c in changed_chunks]
        embed_result = await embed_texts(voyage_api_key, texts)

        rows = []
        for chunk, vector in zip(changed_chunks, embed_result.embeddings):
            key = f"{chunk.note_path}::{chunk.heading}"
            if key in existing_hashes:
                updated += 1
            else:
                added += 1

            rows.append(
                {
                    "note_path": chunk.note_path,
                    "heading": chunk.heading,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "vector": vector,
                }
            )

        upsert_chunks(table, rows)
        build_fts_index(table)
        logger.info(
            "Upserted %d chunks (%d new, %d updated)", len(rows), added, updated
        )

    # Delete stale
    valid_keys = {f"{c.note_path}::{c.heading}" for c in all_chunks}
    deleted = 0
    try:
        if table.count_rows() > 0:
            deleted = delete_stale_chunks(
                table, valid_keys, db=db, existing_df=existing_df
            )
            if deleted:
                # Table was recreated; re-open and rebuild FTS index
                table = get_or_create_table(db)
                build_fts_index(table)
                logger.info("Deleted %d stale chunks", deleted)
    except Exception as e:
        logger.warning("Failed to delete stale chunks: %s", e)

    duration = time.time() - start

    return IndexStats(
        total_notes_scanned=total_notes,
        total_chunks=len(all_chunks),
        chunks_added=added,
        chunks_updated=updated,
        chunks_unchanged=unchanged_count,
        chunks_deleted=deleted,
        duration_seconds=round(duration, 2),
    )
