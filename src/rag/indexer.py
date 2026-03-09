import logging
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import frontmatter

from src.rag.chunker import Chunk, chunk_note
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


@dataclass
class IndexStats:
    total_notes_scanned: int
    total_chunks: int
    chunks_added: int
    chunks_updated: int
    chunks_unchanged: int
    chunks_deleted: int
    duration_seconds: float


def _scan_and_chunk(vault_path: str) -> list[Chunk]:
    vault = Path(vault_path)
    all_chunks: list[Chunk] = []

    for md_file in vault.rglob("*.md"):
        if md_file.is_symlink():
            continue
        rel = md_file.relative_to(vault)
        if any(part.startswith(".") for part in rel.parts):
            continue

        raw = md_file.read_text(encoding="utf-8")
        file_path = str(PurePosixPath(rel))

        try:
            post = frontmatter.loads(raw)
            content = post.content
        except Exception as e:
            logger.debug("Failed to parse frontmatter in %s: %s", file_path, e)
            content = raw

        title = PurePosixPath(file_path).stem
        all_chunks.extend(chunk_note(file_path, title, content))

    return all_chunks


def _build_embed_text(chunk: Chunk) -> str:
    title = PurePosixPath(chunk.note_path).stem
    return f"Note: {title} > {chunk.heading}\n\n{chunk.content}"


async def index_vault(
    vault_path: str, voyage_api_key: str, lancedb_path: str
) -> IndexStats:
    start = time.time()

    # Scan and chunk
    all_chunks = _scan_and_chunk(vault_path)
    note_paths = set(c.note_path for c in all_chunks)
    total_notes = len(note_paths)

    logger.info(f"Scanned {total_notes} notes, {len(all_chunks)} chunks")

    # Compare with existing hashes
    db = get_db(lancedb_path)
    table = get_or_create_table(db)

    existing_hashes = {}
    existing_df = None
    try:
        if table.count_rows() > 0:
            existing_hashes, existing_df = get_existing_data(table)
    except Exception as e:
        logger.warning(f"Failed to load existing data from LanceDB: {e}")

    changed_chunks: list[Chunk] = []
    unchanged_count = 0

    for chunk in all_chunks:
        key = f"{chunk.note_path}::{chunk.heading}"
        if key in existing_hashes and existing_hashes[key] == chunk.content_hash:
            unchanged_count += 1
        else:
            changed_chunks.append(chunk)

    logger.info(f"{len(changed_chunks)} changed, {unchanged_count} unchanged")

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
        logger.info(f"Upserted {len(rows)} chunks ({added} new, {updated} updated)")

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
                logger.info(f"Deleted {deleted} stale chunks")
    except Exception as e:
        logger.warning(f"Failed to delete stale chunks: {e}")

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
