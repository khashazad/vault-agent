# Swagger API Documentation

## Why

API has 16 routes with no descriptions, missing response models, and undocumented fields. FastAPI auto-generates Swagger at `/docs` but it's empty without metadata.

## What

Every route documented with summary, description, tags, and response_model. Every Pydantic field annotated with description. App-level metadata (title, description, version, tag groups). Swagger UI fully usable at `/docs`.

## Context

**Relevant files:**
- `src/server.py` — all 16 route definitions, FastAPI app creation
- `src/models/changesets.py` — `Changeset`, `ProposedChange`, `RoutingInfo`, `ChangeStatusUpdate`, `ApplyRequest`
- `src/models/search.py` — `ChunkInfo`, `IndexResponse`, `SearchResponse`
- `src/models/zotero.py` — all Zotero request/response models
- `src/models/content.py` — `ContentItem`, `SourceMetadata`
- `src/models/vault.py` — `VaultMap`, `VaultNote`, `VaultNoteSummary`

**Patterns to follow:**
- FastAPI's built-in OpenAPI support — `Field(description=...)`, `response_model=`, route `summary`/`description`/`tags`
- Models already use `Field()` for validation (e.g. `max_length`), just need `description` added

**Key decisions:**
- No external docs library — use FastAPI's native OpenAPI/Swagger
- Keep `/docs` (Swagger UI) and `/redoc` (ReDoc) at default paths
- Tag groups: `Health`, `Vault`, `Changesets`, `Zotero`

## Constraints

**Must:**
- Add `response_model` to all routes that currently lack one
- Add `Field(description=...)` to every Pydantic model field used in request/response
- Add `summary`, `description`, `tags` to every route
- Add app-level `description` and `version` to `FastAPI()`

**Must not:**
- Change any route behavior or logic
- Add new dependencies
- Modify existing validation logic (keep `max_length` etc.)

**Out of scope:**
- Authentication docs (no auth exists)
- Example request/response bodies (nice-to-have, not required)
- Custom Swagger UI theme

## Tasks

### T1: App metadata + route documentation in server.py

**Do:**
1. Add `description` and `version` to `FastAPI()` constructor
2. Add `tags` parameter grouping routes: `Health`, `Vault`, `Changesets`, `Zotero`
3. Add `openapi_tags` metadata with descriptions for each tag group
4. Add `summary` and `description` to all 16 routes
5. Add `response_model` to routes missing it:
   - `GET /health` — needs a response model (create `HealthResponse`)
   - `GET /vault/map` — needs a response model (create `VaultMapResponse`)
   - `GET /changesets/{changeset_id}` — `response_model=Changeset`
   - `PATCH /changesets/{changeset_id}/changes/{change_id}` — needs response model
   - `POST /changesets/{changeset_id}/apply` — needs response model
   - `POST /changesets/{changeset_id}/reject` — needs response model
   - `POST /zotero/papers/cache-status` — needs response model
   - `POST /zotero/papers/refresh` — needs response model
   - `POST /zotero/papers/{paper_key}/sync` — `response_model=Changeset`
   - `GET /zotero/status` — needs response model

**Files:** `src/server.py`, `src/models/changesets.py` (new response models), `src/models/zotero.py` (new response models), `src/models/__init__.py`

**Verify:** `uv run python -c "from src.server import app; print(app.openapi())"` — should produce valid OpenAPI JSON with all routes documented

### T2: Field descriptions on all Pydantic models

**Do:** Add `description` to every `Field()` across all model files. Fields without `Field()` get one. Specifically:

`src/models/changesets.py`:
- `RoutingInfo.action` — "Whether to update existing note, create new, or skip"
- `RoutingInfo.target_path` — "Vault-relative path of the target note"
- `RoutingInfo.reasoning` — "Agent's explanation for the routing decision"
- `RoutingInfo.confidence` — "Confidence score 0-1"
- `RoutingInfo.search_results_used` — "Number of search results considered"
- `RoutingInfo.additional_targets` — "Extra note paths affected"
- `RoutingInfo.duplicate_notes` — "Paths of detected duplicate notes"
- `ProposedChange.id` — "Unique change identifier"
- `ProposedChange.tool_name` — "Which write operation to perform"
- `ProposedChange.input` — "Tool input parameters"
- `ProposedChange.original_content` — "Current note content before change (null for new notes)"
- `ProposedChange.proposed_content` — "Full note content after change"
- `ProposedChange.diff` — "Unified diff of the change"
- `ProposedChange.status` — "Current approval status"
- `Changeset` fields, `ChangeStatusUpdate`, `ApplyRequest` — similar

`src/models/search.py`:
- All `ChunkInfo`, `IndexResponse`, `SearchResponse` fields

`src/models/zotero.py`:
- All Zotero model fields

`src/models/content.py`:
- All `ContentItem` and `SourceMetadata` fields

`src/models/vault.py`:
- All `VaultNoteSummary`, `VaultNote`, `VaultMap` fields

**Files:** `src/models/changesets.py`, `src/models/search.py`, `src/models/zotero.py`, `src/models/content.py`, `src/models/vault.py`

**Verify:** `uv run python -c "from src.server import app; import json; schema = app.openapi(); print(json.dumps(schema['components']['schemas'], indent=2))"` — all fields should have `description` in the JSON schema

## Done

- [ ] `uv run python -c "from src.server import app; print(len(app.openapi()['paths']))"` prints 16
- [ ] `uv run python -c "from src.server import app; import json; s=app.openapi(); [print(p,list(s['paths'][p].keys())) for p in sorted(s['paths'])]"` — all routes present with summaries
- [ ] Manual: start server, open `/docs` — all routes visible with descriptions, grouped by tags, request/response schemas documented
- [ ] No regressions: existing API behavior unchanged
