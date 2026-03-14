import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

import anthropic

from src.models import (
    Changeset,
    ContentItem,
    ProposedChange,
    RoutingInfo,
    TokenUsage,
)
from src.config import AppConfig
from src.agent.prompts import build_zotero_synthesis_prompt
from src.agent.diff import generate_diff
from src.store import get_changeset_store

logger = logging.getLogger("vault-agent")

MODELS = {
    "haiku": {
        "id": "claude-haiku-4-5",
        "label": "Haiku 4.5",
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
    "sonnet": {
        "id": "claude-sonnet-4-6",
        "label": "Sonnet 4.6",
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
}
DEFAULT_MODEL = "sonnet"
_BATCH_DISCOUNT = 0.5
_SYNTHESIS_MAX_TOKENS = 8192
_MAX_NOTE_PATH_LENGTH = 100


def _compute_cost(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    model_key: str = DEFAULT_MODEL,
    is_batch: bool = False,
    include_cache_savings: bool = False,
) -> float:
    pricing = MODELS[model_key]
    if include_cache_savings:
        cost = (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
            + cache_write_tokens * pricing["cache_write"] / 1_000_000
            + cache_read_tokens * pricing["cache_read"] / 1_000_000
        )
    else:
        total_input = input_tokens + cache_write_tokens + cache_read_tokens
        cost = (
            total_input * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )
    return cost * _BATCH_DISCOUNT if is_batch else cost


def _build_token_usage(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    api_calls: int,
    tool_calls: int,
    model_key: str = DEFAULT_MODEL,
    is_batch: bool = False,
) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_write_tokens,
        cache_read_tokens=cache_read_tokens,
        api_calls=api_calls,
        tool_calls=tool_calls,
        is_batch=is_batch,
        model=model_key,
        total_cost_usd=_compute_cost(
            input_tokens,
            output_tokens,
            cache_write_tokens,
            cache_read_tokens,
            model_key,
            is_batch,
        ),
    )


# Extract token counts from an Anthropic API response.
def _extract_usage(response) -> tuple[int, int, int, int]:
    u = response.usage
    return (
        u.input_tokens,
        u.output_tokens,
        getattr(u, "cache_creation_input_tokens", 0) or 0,
        getattr(u, "cache_read_input_tokens", 0) or 0,
    )


# Log cache-aware token usage and estimated cost breakdown.
#
# Args:
#     item_count: Number of ContentItems processed.
#     api_calls: Number of Claude API round-trips.
#     tool_call_count: Total tool invocations across all rounds.
#     input_tokens: Non-cached input tokens consumed.
#     output_tokens: Output tokens generated.
#     cache_write_tokens: Tokens written to prompt cache.
#     cache_read_tokens: Tokens read from prompt cache.
def _log_token_usage(
    item_count: int,
    api_calls: int,
    tool_call_count: int,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    model_key: str = DEFAULT_MODEL,
) -> None:
    pricing = MODELS[model_key]
    input_cost = input_tokens * pricing["input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000
    cache_write_cost = cache_write_tokens * pricing["cache_write"] / 1_000_000
    cache_read_cost = cache_read_tokens * pricing["cache_read"] / 1_000_000
    total_cost = _compute_cost(
        input_tokens,
        output_tokens,
        cache_write_tokens,
        cache_read_tokens,
        model_key,
        include_cache_savings=True,
    )

    parts = [f"input={input_tokens} (${input_cost:.4f})"]
    if cache_write_tokens or cache_read_tokens:
        parts.append(f"cache_write={cache_write_tokens} (${cache_write_cost:.4f})")
        parts.append(f"cache_read={cache_read_tokens} (${cache_read_cost:.4f})")
    parts.append(f"output={output_tokens} (${output_cost:.4f})")

    logger.info(
        "LLM usage: %d item(s), %d API call(s), %d tool call(s) | %s | total=$%.4f",
        item_count,
        api_calls,
        tool_call_count,
        ", ".join(parts),
        total_cost,
    )


# Call client.messages.create with exponential backoff on 429/529 errors.
# Retries up to 3 times with 1s base delay.
async def _create_with_retry(client: anthropic.AsyncAnthropic, **kwargs):
    max_retries = 3
    base_delay = 1.0

    for attempt in range(max_retries + 1):
        try:
            return await client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Rate limited (429), retrying in %.1fs (attempt %d/%d)",
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
        except anthropic.APIStatusError as err:
            if err.status_code == 529 and attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "API overloaded (529), retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
            else:
                raise


# Derive a vault-relative path (Papers/<sanitized-title>.md) from Zotero metadata.
def _zotero_note_path(items: list[ContentItem]) -> str:
    meta = items[0].source_metadata
    title = (meta.title if meta and meta.title else "Untitled Paper").strip()
    # Sanitize for filesystem: keep alphanumeric, spaces, hyphens
    sanitized = re.sub(r"[^\w\s\-]", "", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if len(sanitized) > _MAX_NOTE_PATH_LENGTH:
        sanitized = sanitized[:_MAX_NOTE_PATH_LENGTH].rsplit(" ", 1)[0]
    return f"Papers/{sanitized}.md"


# Synthesize a Zotero paper note in a single LLM call (no tool loop).
#
# Sends all annotations to Claude with a Zotero-specific synthesis prompt
# and creates a changeset containing one create_note ProposedChange.
#
# Args:
#     config: App configuration (API keys, vault path).
#     items: Annotation ContentItems from a single Zotero paper.
#     model: Model key to use for synthesis.
#     feedback: User feedback from a rejected previous attempt.
#     previous_reasoning: Agent reasoning from the rejected attempt.
#     parent_changeset_id: ID of the previous changeset if this is a retry.
#
# Returns:
#     Changeset with a single proposed create_note change.
async def generate_zotero_note(
    config: AppConfig,
    items: list[ContentItem],
    model: str = DEFAULT_MODEL,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    parent_changeset_id: str | None = None,
) -> Changeset:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    metadata = items[0].source_metadata

    system, user = build_zotero_synthesis_prompt(
        items, metadata, feedback=feedback, previous_reasoning=previous_reasoning
    )

    response = await _create_with_retry(
        client,
        model=MODELS[model]["id"],
        max_tokens=_SYNTHESIS_MAX_TOKENS,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user}],
    )

    note_content = response.content[0].text
    note_path = _zotero_note_path(items)
    diff = generate_diff(note_path, "", note_content)

    change = ProposedChange(
        id=str(uuid.uuid4()),
        tool_name="create_note",
        input={"path": note_path, "content": note_content},
        original_content=None,
        proposed_content=note_content,
        diff=diff,
    )

    routing = RoutingInfo(
        action="create",
        target_path=note_path,
        reasoning="Single-call Zotero synthesis — new paper note.",
        confidence=1.0,
    )

    inp, out, cw, cr = _extract_usage(response)
    usage = _build_token_usage(
        inp, out, cw, cr, api_calls=1, tool_calls=0, model_key=model
    )

    changeset = Changeset(
        id=str(uuid.uuid4()),
        items=items,
        changes=[change],
        reasoning="Synthesized from paper annotations in a single LLM call.",
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type="zotero",
        routing=routing,
        usage=usage,
        feedback=feedback,
        parent_changeset_id=parent_changeset_id,
    )
    get_changeset_store().set(changeset)

    _log_token_usage(len(items), 1, 0, inp, out, cw, cr, model)

    return changeset


# Submit a Zotero note synthesis via the Anthropic Batch API (50% cost).
#
# Builds the same prompt as generate_zotero_note but submits via
# client.messages.batches.create() for async processing.
#
# Args:
#     config: App configuration (API keys).
#     items: Annotation ContentItems from a single Zotero paper.
#     paper_key: Zotero paper key (used as custom_id in the batch).
#
# Returns:
#     Batch ID string for polling.
async def submit_zotero_note_batch(
    config: AppConfig,
    items: list[ContentItem],
    paper_key: str,
    model: str = DEFAULT_MODEL,
) -> str:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    metadata = items[0].source_metadata

    system, user = build_zotero_synthesis_prompt(items, metadata)

    batch = await client.messages.batches.create(
        requests=[
            {
                "custom_id": paper_key,
                "params": {
                    "model": MODELS[model]["id"],
                    "max_tokens": _SYNTHESIS_MAX_TOKENS,
                    "system": [{"type": "text", "text": system}],
                    "messages": [{"role": "user", "content": user}],
                },
            }
        ]
    )

    logger.info("Batch submitted for paper %s: batch_id=%s", paper_key, batch.id)
    return batch.id


# Poll an Anthropic batch and build a changeset from its result.
#
# Args:
#     config: App configuration.
#     batch_id: Anthropic Batch API batch ID.
#     paper_key: Zotero paper key.
#     items: Original ContentItems (needed for changeset construction).
#
# Returns:
#     Tuple of (status_str, Changeset | None). Changeset is non-None only when complete.
async def poll_zotero_batch(
    config: AppConfig,
    batch_id: str,
    paper_key: str,
    items: list[ContentItem],
) -> tuple[str, Changeset | None]:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)

    batch = await client.messages.batches.retrieve(batch_id)
    status = batch.processing_status

    if status != "ended":
        return status, None

    # Fetch results
    note_content = None
    batch_usage: TokenUsage | None = None
    async for result in client.messages.batches.results(batch_id):
        if result.custom_id == paper_key and result.result.type == "succeeded":
            msg = result.result.message
            note_content = msg.content[0].text
            inp, out, cw, cr = _extract_usage(msg)
            batch_usage = _build_token_usage(
                inp,
                out,
                cw,
                cr,
                api_calls=1,
                tool_calls=0,
                is_batch=True,
            )
            break

    if note_content is None:
        return "failed", None

    note_path = _zotero_note_path(items)
    diff = generate_diff(note_path, "", note_content)

    change = ProposedChange(
        id=str(uuid.uuid4()),
        tool_name="create_note",
        input={"path": note_path, "content": note_content},
        original_content=None,
        proposed_content=note_content,
        diff=diff,
    )

    routing = RoutingInfo(
        action="create",
        target_path=note_path,
        reasoning="Batch API Zotero synthesis — new paper note.",
        confidence=1.0,
    )

    changeset = Changeset(
        id=str(uuid.uuid4()),
        items=items,
        changes=[change],
        reasoning="Synthesized from paper annotations via Batch API.",
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type="zotero",
        routing=routing,
        usage=batch_usage,
    )
    get_changeset_store().set(changeset)

    return "completed", changeset
