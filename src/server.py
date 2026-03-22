import asyncio
import json
import logging
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    CostEstimate,
    FeedbackRequest,
    HealthResponse,
    MigrationJob,
    PaperCacheStatusResponse,
    RefreshResponse,
    RejectResponse,
    TaxonomyCurationRequest,
    TaxonomyCurationResponse,
    TaxonomyProposal,
    VaultConfigRequest,
    VaultConfigResponse,
    VaultHistoryEntry,
    VaultHistoryResponse,
    VaultPickerResponse,
    VaultMapResponse,
    VaultTaxonomy,
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
from src.vault.taxonomy import build_vault_taxonomy, apply_taxonomy_curation
from src.agent.agent import (
    generate_zotero_note,
    submit_zotero_note_batch,
    poll_zotero_batch,
)
from src.agent.changeset import apply_changeset
from src.agent.diff import generate_diff
from src.db import get_changeset_store, get_batch_job_store, get_migration_store, get_settings_store
from src.db.settings import SettingsStore
from src.zotero.background import ZoteroPaperCacheSyncer

from src.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("vault-agent")

paper_cache_syncer: ZoteroPaperCacheSyncer | None = None


# Manage app lifecycle: load config, start/stop the Zotero paper cache syncer.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global paper_cache_syncer
    if not hasattr(app.state, "config"):
        app.state.config = load_config()
    config = app.state.config
    logger.info("vault: %s", config.vault_path or "not configured")
    zotero_ok = bool(config.zotero_api_key and config.zotero_library_id)
    logger.info("zotero: %s", "configured" if zotero_ok else "not configured")
    if zotero_ok and config.vault_path:
        paper_cache_syncer = ZoteroPaperCacheSyncer(config)
        paper_cache_syncer.start()
    yield
    if paper_cache_syncer is not None:
        paper_cache_syncer.stop()


def _get_config(request: Request):
    return request.app.state.config


# Raise HTTP 400 if no vault is configured.
#
# Raises:
#     HTTPException: When vault_path is None.
def _require_vault(request: Request):
    config = _get_config(request)
    if not config.vault_path:
        raise HTTPException(
            status_code=400,
            detail="No vault configured. Select a vault via PUT /vault/config.",
        )


app = FastAPI(
    title="Vault Agent",
    description="AI-powered Obsidian vault integration — processes highlights and Zotero annotations into structured markdown notes via Claude.",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Server health and status"},
        {
            "name": "Vault",
            "description": "Vault structure and note management",
        },
        {
            "name": "Changesets",
            "description": "Changeset review, approval, and application",
        },
        {
            "name": "Zotero",
            "description": "Zotero library sync, papers, and collections",
        },
        {
            "name": "Migration",
            "description": "Vault migration: taxonomy management, per-note migration, and review",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
    _require_vault(request)
    config = _get_config(request)
    vm = build_vault_map(config.vault_path)
    return {"totalNotes": vm.total_notes, "notes": vm.notes}


# Return vault taxonomy with folders, tags, and link targets.
@app.get(
    "/vault/taxonomy",
    response_model=VaultTaxonomy,
    tags=["Vault"],
    summary="Get vault taxonomy",
)
async def vault_taxonomy(request: Request):
    _require_vault(request)
    config = _get_config(request)
    return build_vault_taxonomy(config.vault_path)


# Apply taxonomy curation operations, returning a changeset for review.
@app.post(
    "/vault/taxonomy/apply",
    response_model=TaxonomyCurationResponse,
    tags=["Vault"],
    summary="Apply taxonomy curation",
)
async def vault_taxonomy_apply(request: Request, body: TaxonomyCurationRequest):
    _require_vault(request)
    if not body.operations:
        raise HTTPException(status_code=400, detail="No operations provided")
    config = _get_config(request)
    changeset = apply_taxonomy_curation(config.vault_path, body.operations)
    if not changeset.changes:
        raise HTTPException(status_code=400, detail="No notes affected by these operations")
    get_changeset_store().set(changeset)
    return TaxonomyCurationResponse(
        changeset_id=changeset.id,
        change_count=len(changeset.changes),
    )


# Return current vault configuration.
@app.get(
    "/vault/config",
    response_model=VaultConfigResponse,
    tags=["Vault"],
    summary="Get vault config",
    description="Returns the currently configured vault path and name, or null if no vault is set.",
)
async def vault_config_get(request: Request):
    config = _get_config(request)
    return {
        "vault_path": config.vault_path,
        "vault_name": Path(config.vault_path).name if config.vault_path else None,
    }


# Set the vault path, persisting to DB and updating runtime config.
@app.put(
    "/vault/config",
    response_model=VaultConfigResponse,
    tags=["Vault"],
    summary="Set vault config",
    description="Validate and persist a new vault path. Must be a directory containing .obsidian/.",
)
async def vault_config_set(request: Request, body: VaultConfigRequest):
    p = Path(body.vault_path).expanduser().resolve()
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="Path does not exist or is not a directory")
    if not (p / ".obsidian").is_dir():
        raise HTTPException(status_code=400, detail="Not an Obsidian vault (missing .obsidian/ directory)")

    vault_path = str(p)
    settings = get_settings_store()
    settings.set("vault_path", vault_path)

    # Update vault history
    _update_vault_history(settings, vault_path, p.name)

    config = _get_config(request)
    config.vault_path = vault_path

    # Start Zotero syncer if applicable and not already running
    global paper_cache_syncer
    zotero_ok = bool(config.zotero_api_key and config.zotero_library_id)
    if zotero_ok and paper_cache_syncer is None:
        paper_cache_syncer = ZoteroPaperCacheSyncer(config)
        paper_cache_syncer.start()

    return {
        "vault_path": vault_path,
        "vault_name": p.name,
    }


# Append or update a vault in the history list (max 20, most recent first).
#
# Args:
#     settings: SettingsStore instance.
#     vault_path: Absolute vault path.
#     name: Vault directory name.
def _update_vault_history(settings: SettingsStore, vault_path: str, name: str) -> None:
    raw = settings.get("vault_history")
    history: list[dict] = json.loads(raw) if raw else []
    now = datetime.now(timezone.utc).isoformat()

    history = [h for h in history if h.get("path") != vault_path]
    history.insert(0, {"path": vault_path, "name": name, "last_opened": now})
    history = history[:20]

    settings.set("vault_history", json.dumps(history))


# Open native macOS folder picker via osascript.
@app.post(
    "/vault/picker",
    response_model=VaultPickerResponse,
    tags=["Vault"],
    summary="Open native folder picker",
    description="Opens a macOS Finder dialog to select a vault folder. macOS only.",
)
async def vault_picker():
    if sys.platform != "darwin":
        raise HTTPException(status_code=501, detail="Native picker is only available on macOS")

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select Obsidian Vault")'],
                    capture_output=True,
                    text=True,
                ),
            ),
            timeout=300,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Folder picker timed out")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # osascript returns -128 / "User canceled" on cancel
        if stderr and "User canceled" not in stderr:
            logger.warning("osascript picker failed: %s", stderr)
        return {"path": None, "cancelled": True}

    selected = result.stdout.strip().rstrip("/")
    return {"path": selected, "cancelled": False}


# Return previously opened vaults, filtered to existing directories.
@app.get(
    "/vault/history",
    response_model=VaultHistoryResponse,
    tags=["Vault"],
    summary="Get vault history",
    description="Returns previously opened vaults that still exist on disk.",
)
async def vault_history_get():
    raw = get_settings_store().get("vault_history")
    history: list[dict] = json.loads(raw) if raw else []
    vaults = [
        VaultHistoryEntry(**h)
        for h in history
        if Path(h.get("path", "")).is_dir()
    ]
    return {"vaults": vaults}


# Remove a single vault from history.
@app.delete(
    "/vault/history",
    tags=["Vault"],
    summary="Delete vault history entry",
    description="Removes a single vault from the history list.",
)
async def vault_history_delete(path: str):
    settings = get_settings_store()
    raw = settings.get("vault_history")
    history: list[dict] = json.loads(raw) if raw else []
    history = [h for h in history if h.get("path") != path]
    settings.set("vault_history", json.dumps(history))
    return {"ok": True}


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
    _require_vault(request)
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


# Permanently delete a changeset from the store.
@app.delete(
    "/changesets/{changeset_id}",
    status_code=204,
    tags=["Changesets"],
    summary="Delete changeset",
    description="Permanently delete a changeset regardless of status.",
)
async def delete_changeset(changeset_id: str):
    _get_changeset_or_404(changeset_id)
    get_changeset_store().delete(changeset_id)
    from src.zotero.sync import ZoteroSyncState

    ZoteroSyncState().clear_paper_sync_by_changeset(changeset_id)
    return Response(status_code=204)


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
    _require_vault(request)
    cs = _get_changeset_or_404(changeset_id)
    if cs.status != "revision_requested":
        return JSONResponse(
            {"error": f"Cannot regenerate a {cs.status} changeset"},
            status_code=400,
        )
    config = _get_config(request)
    try:
        new_cs = await generate_zotero_note(
            config,
            cs.items,
            feedback=cs.feedback,
            previous_reasoning=cs.reasoning,
            parent_changeset_id=cs.id,
        )
        return new_cs.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error regenerating changeset")


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
    _require_vault(request)
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
    _require_vault(request)
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


# --- Migration routes ---


# Estimate migration cost, optionally using taxonomy for accurate system prompt sizing.
@app.post(
    "/migration/estimate",
    response_model=CostEstimate,
    tags=["Migration"],
    summary="Estimate migration cost",
)
async def migration_estimate(
    request: Request, model: str = "sonnet", taxonomy_id: str | None = None
):
    _require_vault(request)
    config = _get_config(request)
    from src.migration.migrator import estimate_cost

    return estimate_cost(config.vault_path, model, taxonomy_id)


@app.post(
    "/migration/taxonomy/import",
    response_model=TaxonomyProposal,
    tags=["Migration"],
    summary="Import taxonomy JSON",
)
async def migration_taxonomy_import(request: Request):
    body = await request.json()
    from src.migration.taxonomy import import_taxonomy

    try:
        taxonomy = import_taxonomy(body)
    except (ValueError, Exception) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    get_migration_store().set_taxonomy(taxonomy)
    return taxonomy.model_dump()


@app.get(
    "/migration/taxonomy/{taxonomy_id}",
    response_model=TaxonomyProposal,
    tags=["Migration"],
    summary="Get taxonomy",
)
async def migration_taxonomy_get(taxonomy_id: str):
    t = get_migration_store().get_taxonomy(taxonomy_id)
    if not t:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return t.model_dump()


@app.put(
    "/migration/taxonomy/{taxonomy_id}",
    response_model=TaxonomyProposal,
    tags=["Migration"],
    summary="Update taxonomy",
)
async def migration_taxonomy_update(taxonomy_id: str, request: Request):
    store = get_migration_store()
    existing = store.get_taxonomy(taxonomy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    body = await request.json()
    if "folders" in body:
        existing.folders = body["folders"]
    if "tag_hierarchy" in body:
        from src.models import TagNode

        existing.tag_hierarchy = [
            TagNode(**t) if isinstance(t, dict) else t for t in body["tag_hierarchy"]
        ]
    if "link_targets" in body:
        from src.models import LinkTarget

        existing.link_targets = [
            LinkTarget(**lt) if isinstance(lt, dict) else lt
            for lt in body["link_targets"]
        ]
    existing.status = "curated"
    store.set_taxonomy(existing)
    return existing.model_dump()


@app.post(
    "/migration/taxonomy/{taxonomy_id}/activate",
    response_model=TaxonomyProposal,
    tags=["Migration"],
    summary="Activate taxonomy",
)
async def migration_taxonomy_activate(taxonomy_id: str):
    store = get_migration_store()
    t = store.get_taxonomy(taxonomy_id)
    if not t:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    store.deactivate_all_taxonomies()
    t.status = "active"
    store.set_taxonomy(t)
    return t.model_dump()


# List migration jobs with optional status filter.
@app.get(
    "/migration/jobs",
    tags=["Migration"],
    summary="List migration jobs",
)
async def migration_job_list(
    status: str | None = None,
    limit: int = 10,
):
    jobs = get_migration_store().list_jobs(status=status, limit=limit)
    return {"jobs": [j.model_dump() for j in jobs]}


# Create migration job. Defaults to batch mode (50% cost reduction).
@app.post(
    "/migration/jobs",
    response_model=MigrationJob,
    tags=["Migration"],
    summary="Create migration job",
)
async def migration_job_create(request: Request):
    _require_vault(request)
    config = _get_config(request)
    body = await request.json()
    target_vault = body.get("target_vault")
    taxonomy_id = body.get("taxonomy_id")
    model = body.get("model", "sonnet")
    batch = body.get("batch", True)

    if not target_vault:
        return JSONResponse({"error": "target_vault is required"}, status_code=400)

    target_vault = str(Path(target_vault).expanduser().resolve())

    from src.migration.migrator import (
        create_migration_job,
        run_migration,
        submit_migration_batch,
    )

    job = create_migration_job(config.vault_path, target_vault, taxonomy_id)

    if batch:
        try:
            await submit_migration_batch(config, job.id, model)
            # Re-fetch job after batch submission updated it
            job = get_migration_store().get_job(job.id) or job
        except Exception:
            logger.exception("Batch submission failed, falling back to real-time")
            asyncio.create_task(run_migration(config, job.id, model))
    else:
        asyncio.create_task(run_migration(config, job.id, model))

    return job.model_dump()


# In-memory throttle for batch polling (job_id -> last poll time).
_batch_poll_times: dict[str, float] = {}
_BATCH_POLL_INTERVAL = 30.0


# Get migration job, lazy-polling batch status if applicable.
@app.get(
    "/migration/jobs/{job_id}",
    response_model=MigrationJob,
    tags=["Migration"],
    summary="Get migration job status",
)
async def migration_job_get(job_id: str, request: Request):
    import time

    job = get_migration_store().get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    # Lazy-poll batch status if job is batch-mode and still migrating
    if job.batch_id and job.status == "migrating":
        now = time.monotonic()
        last_poll = _batch_poll_times.get(job_id, 0.0)
        if now - last_poll >= _BATCH_POLL_INTERVAL:
            _batch_poll_times[job_id] = now
            try:
                config = _get_config(request)
                from src.migration.migrator import poll_migration_batch

                await poll_migration_batch(config, job_id)
                job = get_migration_store().get_job(job_id) or job
            except Exception:
                logger.exception("Error polling migration batch for job %s", job_id)

    return job.model_dump()


@app.get(
    "/migration/jobs/{job_id}/notes",
    tags=["Migration"],
    summary="List migration notes",
)
async def migration_job_notes(
    job_id: str,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
):
    store = get_migration_store()
    if not store.get_job(job_id):
        raise HTTPException(status_code=404, detail="Migration job not found")
    notes, total = store.get_notes_by_job(job_id, status, offset, limit)
    return {"notes": [n.model_dump() for n in notes], "total": total}


@app.patch(
    "/migration/jobs/{job_id}/notes/{note_id}",
    tags=["Migration"],
    summary="Update migration note",
)
async def migration_note_update(job_id: str, note_id: str, request: Request):
    store = get_migration_store()
    note = store.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Migration note not found")

    body = await request.json()
    if "status" in body:
        note.status = body["status"]
    if "proposed_content" in body:
        note.proposed_content = body["proposed_content"]
        note.diff = generate_diff(
            note.source_path, note.original_content, body["proposed_content"]
        )
    store.update_note(job_id, note)
    return note.model_dump()


@app.post(
    "/migration/jobs/{job_id}/apply",
    tags=["Migration"],
    summary="Apply approved migration notes",
)
async def migration_job_apply(job_id: str):
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    from src.migration.writer import apply_migration

    job.status = "applying"
    store.set_job(job)

    result = apply_migration(job.source_vault, job.target_vault, job_id)
    job.status = "completed" if not result["failed"] else "failed"
    store.set_job(job)
    return result


# Cancel migration job; also cancels in-flight batch if applicable.
@app.post(
    "/migration/jobs/{job_id}/cancel",
    tags=["Migration"],
    summary="Cancel migration job",
)
async def migration_job_cancel(job_id: str, request: Request):
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    if job.batch_id:
        try:
            config = _get_config(request)
            client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
            await client.messages.batches.cancel(job.batch_id)
        except Exception:
            logger.warning("Failed to cancel batch %s", job.batch_id)

    job.status = "cancelled"
    store.set_job(job)
    return {"id": job_id, "status": "cancelled"}


# Resume a failed migration job (always real-time, even if originally batch).
@app.post(
    "/migration/jobs/{job_id}/resume",
    response_model=MigrationJob,
    tags=["Migration"],
    summary="Resume failed migration job",
)
async def migration_job_resume(job_id: str, request: Request):
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    if job.status != "failed":
        return JSONResponse(
            {"error": f"Only failed jobs can be resumed, current status: {job.status}"},
            status_code=400,
        )

    config = _get_config(request)
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    model = body.get("model", "sonnet") if isinstance(body, dict) else "sonnet"

    from src.migration.migrator import resume_migration

    asyncio.create_task(resume_migration(config, job_id, model))

    # Re-fetch after reset
    job = store.get_job(job_id)
    return job.model_dump()


# Retry a single failed migration note via real-time API.
@app.post(
    "/migration/jobs/{job_id}/notes/{note_id}/retry",
    tags=["Migration"],
    summary="Retry failed migration note",
)
async def migration_note_retry(job_id: str, note_id: str, request: Request):
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    note = store.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Migration note not found")
    if note.status != "failed":
        return JSONResponse(
            {
                "error": f"Only failed notes can be retried, current status: {note.status}"
            },
            status_code=400,
        )

    taxonomy = store.get_taxonomy(job.taxonomy_id) if job.taxonomy_id else None
    if not taxonomy:
        return JSONResponse({"error": "No taxonomy found for job"}, status_code=400)

    config = _get_config(request)
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    model = body.get("model", "sonnet") if isinstance(body, dict) else "sonnet"

    from src.migration.migrator import migrate_note

    try:
        note.status = "processing"
        note.error = None
        store.update_note(job_id, note)

        result = await migrate_note(config, note, taxonomy, model)
        store.update_note(job_id, result)
        return result.model_dump()
    except Exception as err:
        note.status = "failed"
        note.error = str(err)
        store.update_note(job_id, note)
        return _handle_anthropic_error(err, f"Error retrying note {note_id}")


@app.get(
    "/migration/registry",
    tags=["Migration"],
    summary="Get active taxonomy registry",
)
async def migration_registry():
    from src.migration.registry import VaultRegistry

    reg = VaultRegistry.from_active()
    if not reg:
        return JSONResponse({"error": "No active taxonomy"}, status_code=404)
    return {
        "taxonomy_id": reg.taxonomy_id,
        "folders": reg.get_folder_structure(),
        "tags": reg.get_tag_hierarchy(),
        "link_targets": reg.get_link_targets(),
    }


# Serve a file from the configured vault (images, PDFs, etc).
@app.get(
    "/vault/assets/{file_path:path}",
    tags=["Vault"],
    summary="Serve vault asset",
    description="Serve a file from the vault directory. Path traversal is prevented via validate_path.",
)
async def vault_asset(file_path: str, request: Request):
    _require_vault(request)
    from src.vault import validate_path

    config = _get_config(request)
    try:
        resolved = validate_path(config.vault_path, file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not resolved.is_file():
        # Obsidian-style: search vault for file by basename
        target = Path(file_path).name
        vault = Path(config.vault_path)
        for match in vault.rglob(target):
            if match.is_file() and not any(
                p.startswith(".") for p in match.relative_to(vault).parts
            ):
                return FileResponse(match)
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(resolved)


# Check PyInstaller bundle path first, then dev path.
def _find_ui_dist() -> Path | None:
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
        log_config=None,
    )
