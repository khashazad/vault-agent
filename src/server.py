import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import load_config
from src.models import (
    ApplyRequest,
    ApplyResponse,
    Changeset,
    ChangeStatusResponse,
    ChangeStatusUpdate,
    ChunkInfo,
    HealthResponse,
    IndexResponse,
    PaperCacheStatusResponse,
    RefreshResponse,
    RejectResponse,
    SearchResponse,
    VaultMapResponse,
    ZoteroAnnotationItem,
    ZoteroCollection,
    ZoteroCollectionsResponse,
    ZoteroPaperAnnotationsResponse,
    ZoteroPapersResponse,
    ZoteroPaperSummary,
    ZoteroPaperSyncRequest,
    ZoteroStatusResponse,
    ZoteroSyncRequest,
    ZoteroSyncResponse,
)
from src.vault.reader import build_vault_map
from src.agent.agent import generate_changeset
from src.agent.changeset import apply_changeset
from src.store import changeset_store
from src.rag.indexer import index_vault
from src.rag.search import search_vault
from src.rag.embedder import MODEL as EMBEDDING_MODEL
from src.rag.store import VECTOR_DIM
from src.zotero.background import ZoteroPaperCacheSyncer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault-agent")

config = load_config()

paper_cache_syncer: ZoteroPaperCacheSyncer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global paper_cache_syncer
    if config.zotero_api_key and config.zotero_library_id:
        paper_cache_syncer = ZoteroPaperCacheSyncer(config)
        paper_cache_syncer.start()
    yield
    if paper_cache_syncer is not None:
        paper_cache_syncer.stop()


app = FastAPI(
    title="Vault Agent",
    description="AI-powered Obsidian vault integration — processes highlights and Zotero annotations into structured markdown notes via Claude.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Server health and status"},
        {
            "name": "Vault",
            "description": "Vault structure, indexing, and semantic search",
        },
        {
            "name": "Changesets",
            "description": "Changeset review, approval, and application",
        },
        {
            "name": "Zotero",
            "description": "Zotero library sync, papers, and collections",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


def _handle_anthropic_error(err: Exception, context: str) -> JSONResponse:
    """Shared error handler for endpoints that call the Anthropic API."""
    if isinstance(err, anthropic.AuthenticationError):
        return JSONResponse({"error": "Invalid Anthropic API key"}, status_code=401)
    if isinstance(err, anthropic.APIError):
        status = err.status_code or 502
        return JSONResponse({"error": "Upstream API error"}, status_code=status)
    logger.exception(context)
    return JSONResponse({"error": "Internal server error"}, status_code=500)


def _get_changeset_or_404(changeset_id: str):
    """Fetch a changeset, raising HTTP 404 if not found."""
    cs = changeset_store.get(changeset_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Changeset not found")
    return cs


def _reject_changeset(cs):
    """Mark a changeset and all its changes as rejected."""
    cs.status = "rejected"
    for change in cs.changes:
        change.status = "rejected"
    changeset_store.set(cs)


def _require_zotero():
    """Raise 400 if Zotero is not configured."""
    if not config.zotero_api_key or not config.zotero_library_id:
        raise HTTPException(
            status_code=400,
            detail="Zotero is not configured. Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID.",
        )


def _create_zotero_client():
    """Create a ZoteroClient from app config (lazy import to avoid hard dep on pyzotero)."""
    from src.zotero.client import ZoteroClient

    return ZoteroClient(
        library_id=config.zotero_library_id,
        library_type=config.zotero_library_type,
        api_key=config.zotero_api_key,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns server status, whether a vault is configured, and the current UTC timestamp.",
)
async def health():
    return {
        "status": "ok",
        "vaultConfigured": bool(config.vault_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get(
    "/vault/map",
    response_model=VaultMapResponse,
    tags=["Vault"],
    summary="Get vault map",
    description="Returns the vault structure including total note count and per-note summaries with paths, titles, wikilinks, and headings.",
)
async def vault_map():
    try:
        vm = build_vault_map(config.vault_path)
        return {"totalNotes": vm.total_notes, "notes": vm.notes}
    except Exception:
        logger.exception("Error building vault map")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


# --- Changeset routes ---


@app.get(
    "/changesets/{changeset_id}",
    response_model=Changeset,
    tags=["Changesets"],
    summary="Get changeset",
    description="Retrieve a changeset by ID, including all proposed changes, routing info, and current status.",
)
async def get_changeset(changeset_id: str):
    cs = _get_changeset_or_404(changeset_id)
    return cs.model_dump()


@app.patch(
    "/changesets/{changeset_id}/changes/{change_id}",
    response_model=ChangeStatusResponse,
    tags=["Changesets"],
    summary="Update change status",
    description="Set an individual proposed change to approved or rejected.",
)
async def update_change_status(
    changeset_id: str, change_id: str, body: ChangeStatusUpdate
):
    cs = _get_changeset_or_404(changeset_id)

    for change in cs.changes:
        if change.id == change_id:
            change.status = body.status
            changeset_store.set(cs)
            return {"id": change_id, "status": change.status}

    return JSONResponse({"error": "Change not found"}, status_code=404)


@app.post(
    "/changesets/{changeset_id}/apply",
    response_model=ApplyResponse,
    tags=["Changesets"],
    summary="Apply changeset",
    description="Write approved changes to the vault filesystem. Optionally pass specific change_ids; otherwise all approved changes are applied.",
)
async def apply(changeset_id: str, body: ApplyRequest | None = None):
    cs = _get_changeset_or_404(changeset_id)

    if cs.status in ("applied", "rejected", "skipped"):
        return JSONResponse(
            {"error": f"Changeset already {cs.status}"}, status_code=400
        )

    approved_ids = body.change_ids if body else None
    result = apply_changeset(config.vault_path, cs, approved_ids)

    if result["failed"]:
        cs.status = "partially_applied"
    else:
        cs.status = "applied"
    changeset_store.set(cs)

    return result


@app.post(
    "/changesets/{changeset_id}/reject",
    response_model=RejectResponse,
    tags=["Changesets"],
    summary="Reject changeset",
    description="Reject an entire changeset and all its proposed changes.",
)
async def reject(changeset_id: str):
    cs = _get_changeset_or_404(changeset_id)
    _reject_changeset(cs)
    return {"id": cs.id, "status": "rejected"}


# --- RAG routes ---


@app.post(
    "/vault/index",
    response_model=IndexResponse,
    tags=["Vault"],
    summary="Index vault",
    description="Scan the vault, chunk notes by heading, embed via Voyage AI, and upsert into LanceDB. Incremental — only re-embeds changed chunks.",
)
async def vault_index():
    try:
        stats = await index_vault(
            config.vault_path, config.voyage_api_key, config.lancedb_path
        )
        return IndexResponse(success=True, **asdict(stats))
    except Exception:
        logger.exception("Error indexing vault")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get(
    "/vault/search",
    response_model=SearchResponse,
    tags=["Vault"],
    summary="Search vault",
    description="Hybrid semantic + full-text search across indexed vault chunks. Returns ranked results with similarity scores.",
)
async def vault_search(q: str, n: int = 10):
    n = min(n, 100)
    try:
        results = await search_vault(q, config.voyage_api_key, config.lancedb_path, n=n)
        overall_search_type = results[0].search_type if results else "hybrid"
        return SearchResponse(
            query=q,
            results=[
                ChunkInfo(
                    note_path=r.note_path,
                    heading=r.heading,
                    content=r.content,
                    score=r.score,
                    search_type=r.search_type,
                )
                for r in results
            ],
            count=len(results),
            embedding_model=EMBEDDING_MODEL,
            vector_dimensions=VECTOR_DIM,
            search_type=overall_search_type,
        )
    except Exception:
        logger.exception("Error searching vault")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


# --- Zotero routes ---


@app.post(
    "/zotero/sync",
    response_model=ZoteroSyncResponse,
    tags=["Zotero"],
    summary="Sync Zotero library",
    description="Sync papers from Zotero, process annotations through the agent, and create changesets. Supports filtering by collection or paper keys.",
)
async def zotero_sync(body: ZoteroSyncRequest | None = None):
    _require_zotero()
    try:
        from src.zotero.orchestrator import sync_zotero

        result = await sync_zotero(config, body)
        return result
    except Exception:
        logger.exception("Error during Zotero sync")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get(
    "/zotero/collections",
    response_model=ZoteroCollectionsResponse,
    tags=["Zotero"],
    summary="List collections",
    description="List all Zotero collections. Uses cached data when available, falls back to live API fetch.",
)
async def zotero_collections():
    _require_zotero()
    try:
        from src.zotero.sync import ZoteroSyncState

        sync_state = ZoteroSyncState()
        cached = sync_state.get_all_cached_collections()
        if cached:
            items = [ZoteroCollection(**c) for c in cached]
            return ZoteroCollectionsResponse(collections=items, total=len(items))
        # Cache empty — fetch live
        client = _create_zotero_client()
        collections = client.fetch_collections()
        items = [ZoteroCollection(**asdict(c)) for c in collections]
        return ZoteroCollectionsResponse(collections=items, total=len(items))
    except Exception:
        logger.exception("Error fetching Zotero collections")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get(
    "/zotero/papers/cache-status",
    response_model=PaperCacheStatusResponse,
    tags=["Zotero"],
    summary="Paper cache status",
    description="Returns the number of cached papers, when the cache was last updated, and whether a background sync is in progress.",
)
async def zotero_papers_cache_status():
    _require_zotero()
    try:
        from src.zotero.sync import ZoteroSyncState

        sync_state = ZoteroSyncState()
        return {
            "cached_count": sync_state.get_cached_paper_count(),
            "cache_updated_at": sync_state.get_papers_cache_updated_at(),
            "sync_in_progress": paper_cache_syncer.sync_in_progress
            if paper_cache_syncer
            else False,
        }
    except Exception:
        logger.exception("Error fetching paper cache status")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.post(
    "/zotero/papers/refresh",
    response_model=RefreshResponse,
    tags=["Zotero"],
    summary="Refresh paper cache",
    description="Trigger a background sync of the Zotero paper cache. Returns immediately; sync runs asynchronously.",
)
async def zotero_papers_refresh():
    _require_zotero()
    if paper_cache_syncer is None:
        return JSONResponse(
            {"error": "Paper cache syncer is not running."},
            status_code=500,
        )
    paper_cache_syncer.trigger_sync()
    return {"status": "sync_triggered"}


def _to_paper_summary(p: dict, syncs: dict) -> ZoteroPaperSummary:
    """Build a ZoteroPaperSummary from a dict and sync state lookup."""
    sync = syncs.get(p["key"], {})
    return ZoteroPaperSummary(
        key=p["key"],
        title=p["title"],
        authors=p["authors"],
        year=p["year"],
        item_type=p["item_type"],
        last_synced=sync.get("last_synced"),
        changeset_id=sync.get("changeset_id"),
        annotation_count=p.get("annotation_count"),
    )


@app.get(
    "/zotero/papers",
    response_model=ZoteroPapersResponse,
    tags=["Zotero"],
    summary="List papers",
    description="List Zotero papers with pagination, optional collection filter, text search, and sync status filter.",
)
async def zotero_papers(
    collection_key: str | None = None,
    offset: int = 0,
    limit: int = 25,
    search: str | None = None,
    sync_status: str | None = None,
):
    _require_zotero()
    try:
        from src.zotero.sync import ZoteroSyncState

        sync_state = ZoteroSyncState()
        syncs = sync_state.get_all_paper_syncs()

        if collection_key:
            # Live fetch from Zotero, slice in memory
            client = _create_zotero_client()
            papers = client.fetch_papers(collection_key)
            # Enrich with cached annotation counts (API doesn't return them)
            cached_papers = {p["key"]: p for p in sync_state.get_all_cached_papers()}
            paper_dicts = []
            for p in papers:
                d = asdict(p)
                cached = cached_papers.get(d["key"])
                if cached:
                    d["annotation_count"] = cached["annotation_count"]
                paper_dicts.append(d)
            summaries = [_to_paper_summary(d, syncs) for d in paper_dicts]
            if search:
                q = search.lower()
                summaries = [
                    s
                    for s in summaries
                    if q in s.title.lower() or any(q in a.lower() for a in s.authors)
                ]
            if sync_status == "synced":
                summaries = [s for s in summaries if s.last_synced]
            elif sync_status == "unsynced":
                summaries = [
                    s
                    for s in summaries
                    if not s.last_synced and (s.annotation_count or 0) > 0
                ]
            total = len(summaries)
            summaries = summaries[offset : offset + limit]
        else:
            # Use cached papers with SQL pagination
            cached, total = sync_state.get_cached_papers_paginated(
                offset, limit, search, sync_status
            )
            summaries = [_to_paper_summary(p, syncs) for p in cached]

        return ZoteroPapersResponse(
            papers=summaries,
            total=total,
            cache_updated_at=sync_state.get_papers_cache_updated_at(),
        )
    except Exception:
        logger.exception("Error fetching Zotero papers")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.get(
    "/zotero/papers/{paper_key}/annotations",
    response_model=ZoteroPaperAnnotationsResponse,
    tags=["Zotero"],
    summary="Get paper annotations",
    description="Fetch all annotations (highlights, notes) for a specific paper from Zotero.",
)
async def zotero_paper_annotations(paper_key: str):
    _require_zotero()
    try:
        from src.zotero.client import _extract_paper_metadata

        client = _create_zotero_client()
        paper_item = client.fetch_item(paper_key)
        metadata = _extract_paper_metadata(paper_item, paper_key)
        annotations = client.fetch_paper_annotations(paper_key)

        return ZoteroPaperAnnotationsResponse(
            paper_key=paper_key,
            paper_title=metadata.title,
            annotations=[
                ZoteroAnnotationItem(
                    key=a.key,
                    text=a.text,
                    comment=a.comment,
                    color=a.color,
                    page_label=a.page_label,
                    annotation_type=a.annotation_type,
                    date_added=a.date_added,
                )
                for a in annotations
            ],
            total=len(annotations),
        )
    except Exception:
        logger.exception("Error fetching paper annotations")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@app.post(
    "/zotero/papers/{paper_key}/sync",
    response_model=Changeset,
    tags=["Zotero"],
    summary="Sync paper",
    description="Process a single paper's annotations through the agent and return a changeset. Optionally exclude specific annotations.",
)
async def zotero_paper_sync(paper_key: str, body: ZoteroPaperSyncRequest):
    _require_zotero()
    try:
        from src.zotero.client import ZoteroPaper, _extract_paper_metadata
        from src.zotero.orchestrator import _paper_to_content_items
        from src.zotero.sync import ZoteroSyncState

        client = _create_zotero_client()
        paper_item = client.fetch_item(paper_key)
        metadata = _extract_paper_metadata(paper_item, paper_key)
        annotations = client.fetch_paper_annotations(paper_key)

        # Filter out excluded annotations
        if body.excluded_annotation_keys:
            excluded = set(body.excluded_annotation_keys)
            annotations = [a for a in annotations if a.key not in excluded]

        paper = ZoteroPaper(metadata=metadata, annotations=annotations)
        items = _paper_to_content_items(paper)

        if not items:
            return JSONResponse(
                {"error": "No processable annotations found for this paper."},
                status_code=400,
            )

        changeset = await generate_changeset(
            config,
            items=items,
        )

        sync_state = ZoteroSyncState()
        sync_state.set_paper_sync(paper_key, metadata.title, changeset.id)

        return changeset.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error syncing Zotero paper")


@app.get(
    "/zotero/status",
    response_model=ZoteroStatusResponse,
    tags=["Zotero"],
    summary="Zotero status",
    description="Check whether Zotero is configured and return the last sync version and timestamp.",
)
async def zotero_status():
    configured = bool(config.zotero_api_key and config.zotero_library_id)
    last_version = None
    last_synced = None
    if configured:
        try:
            from src.zotero.sync import ZoteroSyncState

            state = ZoteroSyncState()
            last_version = state.get_last_version()
            last_synced = state.get_last_synced()
        except Exception:
            pass
    return {
        "configured": configured,
        "last_version": last_version,
        "last_synced": last_synced,
    }


# Mount static files for the UI (must be last to not shadow API routes)
ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")


if __name__ == "__main__":
    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=config.port,
        reload=True,
    )
