import logging
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
    ChangeStatusUpdate,
    ChunkInfo,
    HighlightInput,
    IndexResponse,
    RegenerateRequest,
    SearchResponse,
)
from src.vault.reader import build_vault_map
from src.agent.agent import generate_changeset
from src.agent.changeset import apply_changeset
from src.store import changeset_store
from src.rag.indexer import index_vault
from src.rag.search import search_vault
from src.rag.embedder import MODEL as EMBEDDING_MODEL
from src.rag.store import VECTOR_DIM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vault-agent")

config = load_config()

app = FastAPI(title="Vault Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _handle_anthropic_error(err: Exception, context: str) -> JSONResponse:
    """Shared error handler for endpoints that call the Anthropic API."""
    if isinstance(err, anthropic.AuthenticationError):
        return JSONResponse({"error": "Invalid Anthropic API key"}, status_code=401)
    if isinstance(err, anthropic.APIError):
        status = err.status_code or 502
        return JSONResponse(
            {"error": f"Anthropic API error: {err.message}"}, status_code=status
        )
    logger.exception(context)
    return JSONResponse({"error": str(err)}, status_code=500)


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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vaultPath": str(config.vault_path),
        "ragEnabled": bool(config.voyage_api_key),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/vault/map")
async def vault_map():
    try:
        vm = build_vault_map(config.vault_path)
        return {"totalNotes": vm.total_notes, "notes": vm.notes}
    except Exception as err:
        return JSONResponse({"error": str(err)}, status_code=500)


# --- Highlight preview ---


@app.post("/highlights/preview")
async def preview_highlight(highlight: HighlightInput):
    try:
        changeset = await generate_changeset(config, highlight)
        return changeset.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error previewing highlight")


# --- Changeset routes ---


@app.get("/changesets")
async def list_changesets():
    changesets = changeset_store.get_all()
    return [
        {
            "id": cs.id,
            "source": cs.highlight.source,
            "change_count": len(cs.changes),
            "status": cs.status,
            "created_at": cs.created_at,
            "routing_action": cs.routing.action if cs.routing else None,
            "routing_target": cs.routing.target_path if cs.routing else None,
            "routing_confidence": cs.routing.confidence if cs.routing else None,
        }
        for cs in changesets
    ]


@app.get("/changesets/{changeset_id}")
async def get_changeset(changeset_id: str):
    cs = _get_changeset_or_404(changeset_id)
    return cs.model_dump()


@app.patch("/changesets/{changeset_id}/changes/{change_id}")
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


@app.post("/changesets/{changeset_id}/apply")
async def apply(changeset_id: str, body: ApplyRequest | None = None):
    cs = _get_changeset_or_404(changeset_id)

    if cs.status in ("applied", "rejected"):
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


@app.post("/changesets/{changeset_id}/reject")
async def reject(changeset_id: str):
    cs = _get_changeset_or_404(changeset_id)
    _reject_changeset(cs)
    return {"id": cs.id, "status": "rejected"}


@app.post("/changesets/{changeset_id}/regenerate")
async def regenerate(changeset_id: str, body: RegenerateRequest):
    cs = _get_changeset_or_404(changeset_id)
    _reject_changeset(cs)

    try:
        new_changeset = await generate_changeset(
            config,
            cs.highlight,
            feedback=body.feedback,
            previous_reasoning=cs.reasoning,
            parent_changeset_id=cs.id,
        )
        return new_changeset.model_dump()
    except Exception as err:
        return _handle_anthropic_error(err, "Error regenerating changeset")


# --- RAG routes ---


@app.post("/vault/index", response_model=IndexResponse)
async def vault_index():
    if not config.voyage_api_key:
        return JSONResponse(
            {"error": "VOYAGE_API_KEY not configured. RAG is disabled."},
            status_code=501,
        )
    try:
        stats = await index_vault(
            config.vault_path, config.voyage_api_key, config.lancedb_path
        )
        return IndexResponse(success=True, **asdict(stats))
    except Exception as err:
        logger.exception("Error indexing vault")
        return JSONResponse({"error": str(err)}, status_code=500)


@app.get("/vault/search", response_model=SearchResponse)
async def vault_search(q: str, n: int = 10):
    if not config.voyage_api_key:
        return JSONResponse(
            {"error": "VOYAGE_API_KEY not configured. RAG is disabled."},
            status_code=501,
        )
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
    except Exception as err:
        logger.exception("Error searching vault")
        return JSONResponse({"error": str(err)}, status_code=500)


# Mount static files for the UI (must be last to not shadow API routes)
ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")


if __name__ == "__main__":
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=config.port,
        reload=True,
    )
