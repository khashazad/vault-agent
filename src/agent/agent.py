import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

import anthropic

from src.models import (
    Changeset,
    ContentItem,
    CreateNoteInput,
    ProposedChange,
    RoutingInfo,
    UpdateNoteInput,
)
from src.config import AppConfig
from src.agent.tools import get_tool_definitions, execute_tool, format_search_results
from src.agent.prompts import (
    build_system_prompt,
    build_batch_user_message,
    build_zotero_synthesis_prompt,
    SOURCE_CONFIGS,
)
from src.rag.search import search_vault
from src.agent.diff import generate_diff
from src.vault import validate_path
from src.vault.reader import build_vault_map
from src.vault.writer import compute_create, compute_update
from src.store import get_changeset_store

logger = logging.getLogger("vault-agent")

MAX_TOOL_CALLS = 15
MODEL = "claude-haiku-4-5-20251001"

# Pricing per million tokens (USD)
_INPUT_COST_PER_MTOK = 1.00
_OUTPUT_COST_PER_MTOK = 5.00
_CACHE_WRITE_COST_PER_MTOK = 1.25
_CACHE_READ_COST_PER_MTOK = 0.10


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
) -> None:
    input_cost = input_tokens * _INPUT_COST_PER_MTOK / 1_000_000
    output_cost = output_tokens * _OUTPUT_COST_PER_MTOK / 1_000_000
    cache_write_cost = cache_write_tokens * _CACHE_WRITE_COST_PER_MTOK / 1_000_000
    cache_read_cost = cache_read_tokens * _CACHE_READ_COST_PER_MTOK / 1_000_000
    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

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


# Scale the max tool call limit based on batch size (min 15, max 40).
def _max_tool_calls(item_count: int) -> int:
    return min(40, max(MAX_TOOL_CALLS, 5 + 3 * item_count))


# Build a truncated search query from item texts for pre-fetch discovery.
def _build_search_query(items: list[ContentItem]) -> str:
    if len(items) == 1:
        return items[0].text[:300]
    return " ".join(item.text[:100] for item in items)[:500]


# Initialize the agent: build client, system prompt, tools, and opening message.
#
# Pre-fetches search results for the items and injects them into the user
# message so the agent starts with relevant vault context.
#
# Args:
#     config: App configuration (API keys, vault path, etc.).
#     items: Content items to process.
#     feedback: Optional user feedback from a previous changeset attempt.
#     previous_reasoning: Optional agent reasoning from a prior run for continuity.
#
# Returns:
#     Tuple of (AsyncAnthropic client, system prompt str, tool defs list, messages list).
async def _init_agent(
    config: AppConfig,
    items: list[ContentItem],
    feedback: str | None = None,
    previous_reasoning: str | None = None,
):
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    is_batch = len(items) > 1
    source_config = SOURCE_CONFIGS.get(items[0].source_type, SOURCE_CONFIGS["web"])
    vault_map = build_vault_map(config.vault_path)
    system_prompt = build_system_prompt(
        vault_map.as_string,
        source_config,
        is_batch=is_batch,
        source_type=items[0].source_type,
    )
    tool_defs = get_tool_definitions()

    # Pre-fetch search results
    search_context = None
    try:
        query = _build_search_query(items)
        results = await search_vault(
            query, config.voyage_api_key, config.lancedb_path, n=7
        )
        if results:
            search_context = format_search_results(results)
            logger.info("Pre-fetched %d search results for agent", len(results))
    except Exception as e:
        logger.warning("Pre-fetch search failed, agent will search manually: %s", e)

    messages: list[dict] = [
        {
            "role": "user",
            "content": build_batch_user_message(
                items,
                source_config,
                feedback,
                previous_reasoning,
                search_context,
            ),
        },
    ]
    return client, system_prompt, tool_defs, messages


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
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < max_retries:
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


# Run the core agent loop: search vault, decide placement, produce a dry-run changeset.
#
# Executes a multi-turn conversation with Claude. The agent searches the vault,
# reports a routing decision, then calls create_note/update_note. All write
# tool calls are intercepted and computed against a virtual filesystem — nothing
# is written to disk. Diffs are generated for each proposed change and the full
# changeset is persisted to SQLite for later approval.
#
# Args:
#     config: App configuration (API keys, vault path, LanceDB path).
#     items: Content items (highlights/annotations) to integrate into the vault.
#     feedback: Optional user feedback to incorporate from a prior attempt.
#     previous_reasoning: Optional agent reasoning from a prior run for context.
#     parent_changeset_id: ID of the previous changeset if this is a retry.
#
# Returns:
#     Changeset with proposed changes, routing info, and agent reasoning.
async def generate_changeset(
    config: AppConfig,
    items: list[ContentItem],
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    parent_changeset_id: str | None = None,
) -> Changeset:

    max_calls = _max_tool_calls(len(items))

    client, system_prompt, tool_defs, messages = await _init_agent(
        config,
        items,
        feedback,
        previous_reasoning,
    )

    proposed_changes: list[ProposedChange] = []
    reasoning_parts: list[str] = []
    routing_info: RoutingInfo | None = None
    search_results_count = 0
    tool_call_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_write_tokens = 0
    total_cache_read_tokens = 0
    api_calls = 0

    # Virtual filesystem for files "created" in preview mode
    virtual_fs: dict[str, str] = {}

    while tool_call_count < max_calls:
        response = await _create_with_retry(
            client,
            model=MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tool_defs,
            messages=messages,
        )

        api_calls += 1
        inp, out, cw, cr = _extract_usage(response)
        total_input_tokens += inp
        total_output_tokens += out
        total_cache_write_tokens += cw
        total_cache_read_tokens += cr

        for block in response.content:
            if block.type == "text":
                reasoning_parts.append(block.text)

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_call_count += 1
                is_error = False
                tool_name = block.name
                tool_input = block.input

                try:
                    if tool_name == "report_routing_decision":
                        routing_info = RoutingInfo(
                            action=tool_input["action"],
                            target_path=tool_input.get("target_path"),
                            reasoning=tool_input["reasoning"],
                            confidence=tool_input["confidence"],
                            search_results_used=search_results_count,
                            duplicate_notes=tool_input.get("duplicate_notes"),
                        )
                        if routing_info.action == "skip":
                            result_content = (
                                "Routing decision recorded: skip. No changes needed — "
                                "this information is already in the vault. "
                                "Summarize your reasoning and finish."
                            )
                        else:
                            result_content = (
                                f"Routing decision recorded: {routing_info.action} "
                                f"{'at ' + routing_info.target_path if routing_info.target_path else '(new note)'}. "
                                f"Now proceed to make the changes."
                            )

                    elif tool_name == "search_vault":
                        result_content = await execute_tool(
                            config.vault_path, tool_name, tool_input, config=config
                        )
                        # Count results from output
                        search_results_count = result_content.count("### Result ")

                    elif tool_name == "read_note":
                        note_path = tool_input["path"]
                        if note_path in virtual_fs:
                            result_content = virtual_fs[note_path]
                        else:
                            result_content = await execute_tool(
                                config.vault_path, tool_name, tool_input, config=config
                            )

                    elif tool_name == "create_note":
                        inp = CreateNoteInput(**tool_input)
                        if inp.path in virtual_fs:
                            raise FileExistsError(
                                f"Note already exists at {inp.path}. Use update_note to modify existing notes."
                            )
                        proposed_content = compute_create(config.vault_path, inp)
                        diff = generate_diff(inp.path, "", proposed_content)

                        change = ProposedChange(
                            id=str(uuid.uuid4()),
                            tool_name="create_note",
                            input=tool_input,
                            original_content=None,
                            proposed_content=proposed_content,
                            diff=diff,
                        )
                        proposed_changes.append(change)
                        virtual_fs[inp.path] = proposed_content

                        result_content = (
                            f"[Preview] Note would be created at {inp.path}"
                        )

                    elif tool_name == "update_note":
                        inp = UpdateNoteInput(**tool_input)
                        if inp.path in virtual_fs:
                            original = virtual_fs[inp.path]
                        else:
                            full_path = validate_path(config.vault_path, inp.path)
                            if not full_path.exists():
                                raise FileNotFoundError(f"Note not found: {inp.path}")
                            original = full_path.read_text(encoding="utf-8")

                        result = compute_update(original, inp)
                        diff = generate_diff(inp.path, original, result)

                        change = ProposedChange(
                            id=str(uuid.uuid4()),
                            tool_name="update_note",
                            input=tool_input,
                            original_content=original,
                            proposed_content=result,
                            diff=diff,
                        )
                        proposed_changes.append(change)
                        virtual_fs[inp.path] = result

                        result_content = (
                            f"[Preview] Note would be updated at {inp.path}"
                        )

                    else:
                        raise ValueError(f"Unknown tool: {tool_name}")

                except Exception as err:
                    logger.warning("Tool %s failed: %s", tool_name, err)
                    is_error = True
                    result_content = f"Error: {err}"

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

    _log_token_usage(
        len(items),
        api_calls,
        tool_call_count,
        total_input_tokens,
        total_output_tokens,
        total_cache_write_tokens,
        total_cache_read_tokens,
    )

    # Fallback: infer routing from first proposed change if agent didn't call report_routing_decision
    if routing_info is None and proposed_changes:
        first = proposed_changes[0]
        routing_info = RoutingInfo(
            action="create" if first.tool_name == "create_note" else "update",
            target_path=first.input.get("path"),
            reasoning="Inferred from agent actions (no explicit routing decision reported).",
            confidence=0.5,
            search_results_used=search_results_count,
        )

    changeset_status = "pending"
    if routing_info and routing_info.action == "skip":
        changeset_status = "skipped"

    changeset = Changeset(
        id=str(uuid.uuid4()),
        items=items,
        changes=proposed_changes,
        reasoning="".join(reasoning_parts),
        status=changeset_status,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type=items[0].source_type,
        routing=routing_info,
        feedback=feedback,
        parent_changeset_id=parent_changeset_id,
    )
    get_changeset_store().set(changeset)

    return changeset


# Derive a vault-relative path (Papers/<sanitized-title>.md) from Zotero metadata.
def _zotero_note_path(items: list[ContentItem]) -> str:
    meta = items[0].source_metadata
    title = (meta.title if meta and meta.title else "Untitled Paper").strip()
    # Sanitize for filesystem: keep alphanumeric, spaces, hyphens
    sanitized = re.sub(r"[^\w\s\-]", "", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if len(sanitized) > 100:
        sanitized = sanitized[:100].rsplit(" ", 1)[0]
    return f"Papers/{sanitized}.md"


# Synthesize a Zotero paper note in a single LLM call (no tool loop).
#
# Sends all annotations to Claude with a Zotero-specific synthesis prompt
# and creates a changeset containing one create_note ProposedChange.
# Faster than generate_changeset since it skips search/routing.
#
# Args:
#     config: App configuration (API keys, vault path).
#     items: Annotation ContentItems from a single Zotero paper.
#
# Returns:
#     Changeset with a single proposed create_note change.
async def generate_zotero_note(
    config: AppConfig,
    items: list[ContentItem],
) -> Changeset:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    metadata = items[0].source_metadata

    system, user = build_zotero_synthesis_prompt(items, metadata)

    response = await _create_with_retry(
        client,
        model=MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
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

    changeset = Changeset(
        id=str(uuid.uuid4()),
        items=items,
        changes=[change],
        reasoning="Synthesized from paper annotations in a single LLM call.",
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type="zotero",
        routing=routing,
    )
    get_changeset_store().set(changeset)

    _log_token_usage(len(items), 1, 0, *_extract_usage(response))

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
) -> str:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    metadata = items[0].source_metadata

    system, user = build_zotero_synthesis_prompt(items, metadata)

    batch = await client.messages.batches.create(
        requests=[
            {
                "custom_id": paper_key,
                "params": {
                    "model": MODEL,
                    "max_tokens": 8192,
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
    async for result in client.messages.batches.results(batch_id):
        if result.custom_id == paper_key and result.result.type == "succeeded":
            note_content = result.result.message.content[0].text
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
    )
    get_changeset_store().set(changeset)

    return "completed", changeset
