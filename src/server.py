import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import load_config
from src.models import (
    ApplyRequest,
    ApplyResponse,
    BatchJobStatusResponse,
    ChangeContentUpdate,
    Changeset,
    ChangesetListResponse,
    ChangesetSummary,
    ChangeStatusResponse,
    ChangeStatusUpdate,
    ChunkInfo,
    FeedbackRequest,
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
from src.agent.agent import (
    generate_zotero_note,
    submit_zotero_note_batch,
    poll_zotero_batch,
)
from src.agent.changeset import apply_changeset
from src.store import get_changeset_store, get_batch_job_store
from src.rag.indexer import index_vault
from src.rag.search import search_vault
from src.rag.embedder import MODEL as EMBEDDING_MODEL
from src.rag.store import VECTOR_DIM
from src.zotero.background import ZoteroPaperCacheSyncer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault-agent")

paper_cache_syncer: ZoteroPaperCacheSyncer | None = None


# Manage app lifecycle: load config, start/stop the Zotero paper cache syncer.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global paper_cache_syncer
    if not hasattr(app.state, "config"):
        app.state.config = load_config()
    config = app.state.config
    if config.zotero_api_key and config.zotero_library_id:
        paper_cache_syncer = ZoteroPaperCacheSyncer(config)
        paper_cache_syncer.start()
    yield
    if paper_cache_syncer is not None:
        paper_cache_syncer.stop()


def _get_config(request: Request):
    return request.app.state.config


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


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"error": "Internal server error"}, status_code=500)


# Map Anthropic SDK exceptions to appropriate HTTP error responses.
#
# Args:
#     err: The caught exception.
#     context: Log message prefix for unexpected errors.
#
# Returns:
#     JSONResponse with appropriate status code (401, 502, or 500).
def _handle_anthropic_error(err: Exception, context: str) -> JSONResponse:
    if isinstance(err, anthropic.AuthenticationError):
        return JSONResponse({"error": "Invalid Anthropic API key"}, status_code=401)
    if isinstance(err, anthropic.APIError):
        status = err.status_code or 502
        return JSONResponse({"error": "Upstream API error"}, status_code=status)
    logger.exception(context)
    return JSONResponse({"error": "Internal server error"}, status_code=500)


# Fetch a changeset by ID, raising HTTP 404 if not found.
#
# Args:
#     changeset_id: The changeset ID to look up.
#
# Returns:
#     The Changeset object.
#
# Raises:
#     HTTPException: When changeset ID does not exist in the store.
def _get_changeset_or_404(changeset_id: str):
    cs = get_changeset_store().get(changeset_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Changeset not found")
    return cs


# Mark a changeset and all its changes as rejected, then persist.
#
# Args:
#     cs: The changeset to reject.
def _reject_changeset(cs):
    cs.status = "rejected"
    for change in cs.changes:
        change.status = "rejected"
    get_changeset_store().set(cs)


# Raise HTTP 400 if Zotero API key or library ID is not configured.
#
# Raises:
#     HTTPException: When Zotero credentials are missing.
def _require_zotero(request: Request):
    config = _get_config(request)
    if not config.zotero_api_key or not config.zotero_library_id:
        raise HTTPException(
            status_code=400,
            detail="Zotero is not configured. Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID.",
        )


# Create a ZoteroClient from app config (lazy import to avoid hard dep on pyzotero).
#
# Returns:
#     Configured ZoteroClient instance.
def _create_zotero_client(request: Request):
    from src.zotero.client import ZoteroClient

    config = _get_config(request)
    return ZoteroClient(
        library_id=config.zotero_library_id,
        library_type=config.zotero_library_type,
        api_key=config.zotero_api_key,
    )


# Return server health status and vault configuration state.
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns server status, whether a vault is configured, and the current UTC timestamp.",
)
async def health(request: Request):
    config = _get_config(request)
    return {
        "status": "ok",
        "vaultConfigured": bool(config.vault_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Return vault structure with note summaries.
@app.get(
    "/vault/map",
    response_model=VaultMapResponse,
    tags=["Vault"],
    summary="Get vault map",
    description="Returns the vault structure including total note count and per-note summaries with paths, titles, wikilinks, and headings.",
)
async def vault_map(request: Request):
    config = _get_config(request)
    vm = build_vault_map(config.vault_path)
    return {"totalNotes": vm.total_notes, "notes": vm.notes}


# --- Changeset routes ---


# List changesets with optional status filter and pagination.
@app.get(
    "/changesets",
    response_model=ChangesetListResponse,
    tags=["Changesets"],
    summary="List changesets",
    description="List all changesets with optional status filter and pagination.",
)
async def list_changesets(
    status: str | None = None,
    offset: int = 0,
    limit: int = 25,
):
    changesets, total = get_changeset_store().get_all_filtered(status, offset, limit)
    summaries = [
        ChangesetSummary(
            id=cs.id,
            status=cs.status,
            created_at=cs.created_at,
            source_type=cs.source_type,
            change_count=len(cs.changes),
            routing=cs.routing,
            feedback=cs.feedback,
            parent_changeset_id=cs.parent_changeset_id,
        )
        for cs in changesets
    ]
    return ChangesetListResponse(changesets=summaries, total=total)


# Retrieve a changeset by ID.
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


# Update an individual proposed change: status, content, or both.
@app.patch(
    "/changesets/{changeset_id}/changes/{change_id}",
    response_model=ChangeStatusResponse,
    tags=["Changesets"],
    summary="Update change",
    description="Update a proposed change's status and/or content. When content is updated, the diff is recalculated.",
)
async def update_change_status(
    changeset_id: str, change_id: str, body: ChangeContentUpdate
):
    cs = _get_changeset_or_404(changeset_id)

    for change in cs.changes:
        if change.id == change_id:
            if body.proposed_content is not None:
                from src.agent.diff import generate_diff

                change.proposed_content = body.proposed_content
                change.diff = generate_diff(
                    change.input.get("path", ""),
                    change.original_content or "",
                    body.proposed_content,
                )
            if body.status is not None:
                change.status = body.status
            get_changeset_store().set(cs)
            return {"id": change_id, "status": change.status}

    return JSONResponse({"error": "Change not found"}, status_code=404)


# Apply approved changes from a changeset to the vault filesystem.
@app.post(
    "/changesets/{changeset_id}/apply",
    response_model=ApplyResponse,
    tags=["Changesets"],
    summary="Apply changeset",
    description="Write approved changes to the vault filesystem. Optionally pass specific change_ids; otherwise all approved changes are applied.",
)
async def apply(changeset_id: str, request: Request, body: ApplyRequest | None = None):
    cs = _get_changeset_or_404(changeset_id)

    if cs.status in ("applied", "rejected", "skipped"):
        return JSONResponse(
            {"error": f"Changeset already {cs.status}"}, status_code=400
        )

    config = _get_config(request)
    approved_ids = body.change_ids if body else None
    result = apply_changeset(config.vault_path, cs, approved_ids)

    if result["failed"]:
        cs.status = "partially_applied"
    else:
        cs.status = "applied"
    get_changeset_store().set(cs)

    return result


# Reject an entire changeset and all its proposed changes.
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


# Submit feedback on a changeset and request revision.
@app.post(
    "/changesets/{changeset_id}/request-changes",
    tags=["Changesets"],
    summary="Request changes",
    description="Submit feedback and mark a changeset for revision. Status must be pending or partially_applied.",
)
async def request_changes(changeset_id: str, body: FeedbackRequest):
    cs = _get_changeset_or_404(changeset_id)
    if cs.status not in ("pending", "partially_applied"):
        return JSONResponse(
            {"error": f"Cannot request changes on a {cs.status} changeset"},
            status_code=400,
        )
    cs.status = "revision_requested"
    cs.feedback = body.feedback
    get_changeset_store().set(cs)
    return {"id": cs.id, "status": cs.status, "feedback": cs.feedback}


# Regenerate a changeset using stored feedback.
@app.post(
    "/changesets/{changeset_id}/regenerate",
    response_model=Changeset,
    tags=["Changesets"],
    summary="Regenerate changeset",
    description="Re-run the agent with stored feedback from request-changes. Status must be revision_requested.",
)
async def regenerate(changeset_id: str, request: Request):
    cs = _get_changeset_or_404(changeset_id)
    if cs.status != "revision_requested":
        return JSONResponse(
            {"error": f"Cannot regenerate a {cs.status} changeset"},
            status_code=400,
        )
    config = _get_config(request)
    try:
        from src.agent.agent import generate_changeset

        new_cs = await generate_changeset(
            config,
            cs.items,
            feedback=cs.feedback,
            previous_reasoning=cs.reasoning,
            parent_changeset_id=cs.id,
        )
        return new_cs.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error regenerating changeset")


# --- RAG routes ---


# Index vault notes into LanceDB for semantic search.
@app.post(
    "/vault/index",
    response_model=IndexResponse,
    tags=["Vault"],
    summary="Index vault",
    description="Scan the vault, chunk notes by heading, embed via Voyage AI, and upsert into LanceDB. Incremental — only re-embeds changed chunks.",
)
async def vault_index(request: Request):
    config = _get_config(request)
    stats = await index_vault(
        config.vault_path, config.voyage_api_key, config.lancedb_path
    )
    return IndexResponse(success=True, **asdict(stats))


# Hybrid semantic + full-text search across indexed vault chunks.
@app.get(
    "/vault/search",
    response_model=SearchResponse,
    tags=["Vault"],
    summary="Search vault",
    description="Hybrid semantic + full-text search across indexed vault chunks. Returns ranked results with similarity scores.",
)
async def vault_search(q: str, request: Request, n: int = 10):
    config = _get_config(request)
    n = min(n, 100)
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


# --- Zotero routes ---


# Sync papers from Zotero and create changesets from annotations.
@app.post(
    "/zotero/sync",
    response_model=ZoteroSyncResponse,
    tags=["Zotero"],
    summary="Sync Zotero library",
    description="Sync papers from Zotero, process annotations through the agent, and create changesets. Supports filtering by collection or paper keys.",
)
async def zotero_sync(request: Request, body: ZoteroSyncRequest | None = None):
    _require_zotero(request)
    config = _get_config(request)
    from src.zotero.orchestrator import sync_zotero

    return await sync_zotero(config, body)


# List all Zotero collections from cache or live API.
@app.get(
    "/zotero/collections",
    response_model=ZoteroCollectionsResponse,
    tags=["Zotero"],
    summary="List collections",
    description="List all Zotero collections. Uses cached data when available, falls back to live API fetch.",
)
async def zotero_collections(request: Request):
    _require_zotero(request)
    from src.zotero.sync import ZoteroSyncState

    sync_state = ZoteroSyncState()
    cached = sync_state.get_all_cached_collections()
    if cached:
        items = [ZoteroCollection(**c) for c in cached]
        return ZoteroCollectionsResponse(collections=items, total=len(items))
    # Cache empty — fetch live
    client = _create_zotero_client(request)
    collections = client.fetch_collections()
    items = [ZoteroCollection(**asdict(c)) for c in collections]
    return ZoteroCollectionsResponse(collections=items, total=len(items))


# Return paper cache count, last update time, and sync progress.
@app.get(
    "/zotero/papers/cache-status",
    response_model=PaperCacheStatusResponse,
    tags=["Zotero"],
    summary="Paper cache status",
    description="Returns the number of cached papers, when the cache was last updated, and whether a background sync is in progress.",
)
async def zotero_papers_cache_status(request: Request):
    _require_zotero(request)
    from src.zotero.sync import ZoteroSyncState

    sync_state = ZoteroSyncState()
    return {
        "cached_count": sync_state.get_cached_paper_count(),
        "cache_updated_at": sync_state.get_papers_cache_updated_at(),
        "sync_in_progress": paper_cache_syncer.sync_in_progress
        if paper_cache_syncer
        else False,
    }


# Trigger a background refresh of the Zotero paper cache.
@app.post(
    "/zotero/papers/refresh",
    response_model=RefreshResponse,
    tags=["Zotero"],
    summary="Refresh paper cache",
    description="Trigger a background sync of the Zotero paper cache. Returns immediately; sync runs asynchronously.",
)
async def zotero_papers_refresh(request: Request):
    _require_zotero(request)
    if paper_cache_syncer is None:
        return JSONResponse(
            {"error": "Paper cache syncer is not running."},
            status_code=500,
        )
    paper_cache_syncer.trigger_sync()
    return {"status": "sync_triggered"}


# Build a ZoteroPaperSummary from a paper dict and sync state lookup.
#
# Args:
#     p: Paper dict with key, title, authors, year, item_type, annotation_count.
#     syncs: Dict mapping paper keys to sync info (last_synced, changeset_id).
#
# Returns:
#     ZoteroPaperSummary with sync metadata attached.
def _to_paper_summary(p: dict, syncs: dict) -> ZoteroPaperSummary:
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


# List Zotero papers with pagination, collection filter, and search.
@app.get(
    "/zotero/papers",
    response_model=ZoteroPapersResponse,
    tags=["Zotero"],
    summary="List papers",
    description="List Zotero papers with pagination, optional collection filter, text search, and sync status filter.",
)
async def zotero_papers(
    request: Request,
    collection_key: str | None = None,
    offset: int = 0,
    limit: int = 25,
    search: str | None = None,
    sync_status: str | None = None,
):
    _require_zotero(request)
    from src.zotero.sync import ZoteroSyncState

    sync_state = ZoteroSyncState()
    syncs = sync_state.get_all_paper_syncs()

    if collection_key:
        # Live fetch from Zotero, slice in memory
        client = _create_zotero_client(request)
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


# Fetch all annotations for a specific paper from Zotero.
@app.get(
    "/zotero/papers/{paper_key}/annotations",
    response_model=ZoteroPaperAnnotationsResponse,
    tags=["Zotero"],
    summary="Get paper annotations",
    description="Fetch all annotations (highlights, notes) for a specific paper from Zotero.",
)
async def zotero_paper_annotations(paper_key: str, request: Request):
    _require_zotero(request)
    from src.zotero.client import _extract_paper_metadata

    client = _create_zotero_client(request)
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


# Process a single paper's annotations through the agent and return a changeset.
@app.post(
    "/zotero/papers/{paper_key}/sync",
    response_model=Changeset,
    tags=["Zotero"],
    summary="Sync paper",
    description="Process a single paper's annotations through the agent and return a changeset. Optionally exclude specific annotations.",
)
async def zotero_paper_sync(
    paper_key: str, request: Request, body: ZoteroPaperSyncRequest
):
    _require_zotero(request)
    config = _get_config(request)
    try:
        from src.zotero.client import ZoteroPaper, _extract_paper_metadata
        from src.zotero.orchestrator import _paper_to_content_items
        from src.zotero.sync import ZoteroSyncState

        client = _create_zotero_client(request)
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

        if body.batch:
            # Submit via Batch API for 50% cost reduction
            import json

            batch_id = await submit_zotero_note_batch(
                config, items, paper_key, model=body.model
            )
            items_json = json.dumps([item.model_dump() for item in items])
            get_batch_job_store().set(
                paper_key=paper_key,
                batch_id=batch_id,
                status="pending",
                items_json=items_json,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            return JSONResponse(
                {
                    "batch_id": batch_id,
                    "status": "pending",
                    "paper_key": paper_key,
                    "message": "Submitted via Batch API. Poll GET /zotero/papers/{paper_key}/batch-status for result.",
                },
                status_code=202,
            )

        changeset = await generate_zotero_note(config, items, model=body.model)

        sync_state = ZoteroSyncState()
        sync_state.set_paper_sync(paper_key, metadata.title, changeset.id)

        return changeset.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error syncing Zotero paper")


# Poll batch job status for a paper; finalize changeset when complete.
@app.get(
    "/zotero/papers/{paper_key}/batch-status",
    response_model=BatchJobStatusResponse,
    tags=["Zotero"],
    summary="Batch job status",
    description="Poll the Anthropic Batch API for a paper's async synthesis job. When complete, creates the changeset.",
)
async def zotero_paper_batch_status(paper_key: str, request: Request):
    _require_zotero(request)
    config = _get_config(request)
    job = get_batch_job_store().get(paper_key)
    if not job:
        raise HTTPException(status_code=404, detail="No batch job found for this paper")

    if job["status"] in ("completed", "failed"):
        return BatchJobStatusResponse(
            paper_key=paper_key,
            batch_id=job["batch_id"],
            status=job["status"],
            changeset_id=job["changeset_id"],
            created_at=job["created_at"],
        )

    try:
        import json
        from src.models import ContentItem
        from src.zotero.sync import ZoteroSyncState

        items = [ContentItem(**d) for d in json.loads(job["items_json"])]
        status, changeset = await poll_zotero_batch(
            config, job["batch_id"], paper_key, items
        )

        changeset_id = None
        if status == "completed" and changeset:
            changeset_id = changeset.id
            get_batch_job_store().update_status(paper_key, "completed", changeset_id)
            meta = items[0].source_metadata
            title = meta.title if meta else "Unknown"
            sync_state = ZoteroSyncState()
            sync_state.set_paper_sync(paper_key, title, changeset.id)
        elif status == "ended":
            # Ended but no result for this paper
            get_batch_job_store().update_status(paper_key, "failed")
            status = "failed"
        else:
            get_batch_job_store().update_status(paper_key, status)

        return BatchJobStatusResponse(
            paper_key=paper_key,
            batch_id=job["batch_id"],
            status=status,
            changeset_id=changeset_id,
            created_at=job["created_at"],
        )
    except Exception:
        logger.exception("Error polling batch status for paper %s", paper_key)
        return JSONResponse({"error": "Internal server error"}, status_code=500)


# Check Zotero configuration status and last sync info.
@app.get(
    "/zotero/status",
    response_model=ZoteroStatusResponse,
    tags=["Zotero"],
    summary="Zotero status",
    description="Check whether Zotero is configured and return the last sync version and timestamp.",
)
async def zotero_status(request: Request):
    config = _get_config(request)
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
def _find_ui_dist() -> Path | None:
    """Check PyInstaller bundle path first, then dev path."""
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "ui" / "dist"
        if bundled.exists():
            return bundled
    dev = Path(__file__).parent.parent / "ui" / "dist"
    if dev.exists():
        return dev
    return None


ui_dist = _find_ui_dist()
if ui_dist:
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")


if __name__ == "__main__":
    _config = load_config()
    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=_config.port,
        reload=True,
    )
