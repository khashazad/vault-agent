import asyncio
import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel

from src.config import load_config
from src.models import (
    HighlightInput,
    AgentStreamEvent,
    IndexResponse,
    SearchResponse,
    ChunkInfo,
)
from src.vault.reader import build_vault_map
from src.agent.agent import process_highlight, process_highlight_preview
from src.agent.changeset import apply_changeset
from src.store import changeset_store
from src.rag.indexer import index_vault
from src.rag.search import search_vault
from src.rag import embedder as rag_embedder
from src.rag import store as rag_store

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

# Lock to prevent concurrent preview processing
_preview_lock = asyncio.Lock()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code}")
    return response


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


@app.post("/highlights/process")
async def process(highlight: HighlightInput):
    try:
        result = await process_highlight(config, highlight)
        return result
    except anthropic.AuthenticationError:
        return JSONResponse({"error": "Invalid Anthropic API key"}, status_code=401)
    except anthropic.APIError as err:
        status = err.status_code or 502
        return JSONResponse(
            {"error": f"Anthropic API error: {err.message}"}, status_code=status
        )
    except Exception as err:
        logger.exception("Error processing highlight")
        return JSONResponse({"error": str(err)}, status_code=500)


# --- Preview / Changeset routes ---


@app.post("/highlights/preview")
async def preview(highlight: HighlightInput):
    if _preview_lock.locked():
        return JSONResponse(
            {"error": "A preview is already in progress. Please wait."},
            status_code=409,
        )

    async def event_stream():
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def on_event(event: AgentStreamEvent):
            data = json.dumps(event.model_dump())
            await queue.put(f"event: {event.type}\ndata: {data}\n\n")

        async def run_agent():
            async with _preview_lock:
                try:
                    await process_highlight_preview(config, highlight, on_event)
                except anthropic.AuthenticationError:
                    err = json.dumps(
                        {
                            "type": "error",
                            "data": {"message": "Invalid Anthropic API key"},
                        }
                    )
                    await queue.put(f"event: error\ndata: {err}\n\n")
                except Exception as err:
                    logger.exception("Error in preview stream")
                    error_data = json.dumps(
                        {"type": "error", "data": {"message": str(err)}}
                    )
                    await queue.put(f"event: error\ndata: {error_data}\n\n")
                finally:
                    await queue.put(None)  # Signal done

        task = asyncio.create_task(run_agent())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/changesets")
async def list_changesets():
    changeset_store.cleanup()
    changesets = changeset_store.get_all()
    return [
        {
            "id": cs.id,
            "source": cs.highlight.source,
            "change_count": len(cs.changes),
            "status": cs.status,
            "created_at": cs.created_at,
        }
        for cs in changesets
    ]


@app.get("/changesets/{changeset_id}")
async def get_changeset(changeset_id: str):
    cs = changeset_store.get(changeset_id)
    if not cs:
        return JSONResponse({"error": "Changeset not found"}, status_code=404)
    return cs.model_dump()


class ChangeStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]


@app.patch("/changesets/{changeset_id}/changes/{change_id}")
async def update_change_status(
    changeset_id: str, change_id: str, body: ChangeStatusUpdate
):
    cs = changeset_store.get(changeset_id)
    if not cs:
        return JSONResponse({"error": "Changeset not found"}, status_code=404)

    for change in cs.changes:
        if change.id == change_id:
            change.status = body.status
            changeset_store.set(cs)
            return {"id": change_id, "status": change.status}

    return JSONResponse({"error": "Change not found"}, status_code=404)


class ApplyRequest(BaseModel):
    change_ids: list[str] | None = None


@app.post("/changesets/{changeset_id}/apply")
async def apply(changeset_id: str, body: ApplyRequest | None = None):
    cs = changeset_store.get(changeset_id)
    if not cs:
        return JSONResponse({"error": "Changeset not found"}, status_code=404)

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
    cs = changeset_store.get(changeset_id)
    if not cs:
        return JSONResponse({"error": "Changeset not found"}, status_code=404)

    cs.status = "rejected"
    for change in cs.changes:
        change.status = "rejected"
    changeset_store.set(cs)

    return {"id": cs.id, "status": "rejected"}


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
        return IndexResponse(success=True, **dataclasses.asdict(stats))
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
            embedding_model=rag_embedder.MODEL,
            vector_dimensions=rag_store.VECTOR_DIM,
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
