import asyncio
import logging
import uuid
from datetime import datetime, timezone

import anthropic

from src.models import (
    Changeset,
    CreateNoteInput,
    HighlightInput,
    ProposedChange,
    RoutingInfo,
    UpdateNoteInput,
)
from src.config import AppConfig
from src.agent.tools import get_tool_definitions, execute_tool, format_search_results
from src.agent.prompts import build_system_prompt, build_batch_user_message
from src.rag.search import search_vault
from src.agent.diff import generate_diff
from src.vault import validate_path
from src.vault.reader import build_vault_map
from src.vault.writer import compute_create, compute_update
from src.store import changeset_store

logger = logging.getLogger("vault-agent")

MAX_TOOL_CALLS = 15
MODEL = "claude-haiku-4-5-20251001"

# Pricing per million tokens (USD)
_INPUT_COST_PER_MTOK = 1.00
_OUTPUT_COST_PER_MTOK = 5.00
_CACHE_WRITE_COST_PER_MTOK = 1.25
_CACHE_READ_COST_PER_MTOK = 0.10


def _max_tool_calls(highlight_count: int) -> int:
    """Scale tool call limit with batch size."""
    return min(40, max(MAX_TOOL_CALLS, 5 + 3 * highlight_count))


def _build_search_query(highlights: list[HighlightInput]) -> str:
    """Build a search query from highlight texts for pre-fetching."""
    if len(highlights) == 1:
        return highlights[0].text[:300]
    parts = [h.text[:100] for h in highlights]
    combined = " ".join(parts)
    return combined[:500]


async def _init_agent(
    config: AppConfig,
    highlights: list[HighlightInput],
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    paper_metadata: dict | None = None,
):
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    is_batch = len(highlights) > 1
    vault_map = build_vault_map(config.vault_path)
    system_prompt = build_system_prompt(vault_map.as_string, is_batch=is_batch)
    tool_defs = get_tool_definitions()

    # Pre-fetch search results
    search_context = None
    try:
        query = _build_search_query(highlights)
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
                highlights,
                feedback,
                previous_reasoning,
                search_context,
                paper_metadata=paper_metadata,
            ),
        },
    ]
    return client, system_prompt, tool_defs, messages


async def _create_with_retry(client: anthropic.AsyncAnthropic, **kwargs):
    """Call client.messages.create with exponential backoff on rate limit (429)
    and overloaded (529) errors. Retries up to 3 times with 1s base delay."""
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


async def generate_changeset(
    config: AppConfig,
    highlight: HighlightInput | None = None,
    highlights: list[HighlightInput] | None = None,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    parent_changeset_id: str | None = None,
    paper_metadata: dict | None = None,
) -> Changeset:
    """Run the agent to search, decide placement, and generate changes.
    Accepts a single highlight or a list. Returns a Changeset with proposed changes (no writes to disk)."""

    # Normalize to list
    if highlights is None:
        if highlight is None:
            raise ValueError("Either highlight or highlights must be provided")
        highlights = [highlight]

    max_calls = _max_tool_calls(len(highlights))

    client, system_prompt, tool_defs, messages = await _init_agent(
        config,
        highlights,
        feedback,
        previous_reasoning,
        paper_metadata=paper_metadata,
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
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        total_cache_write_tokens += (
            getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        )
        total_cache_read_tokens += (
            getattr(response.usage, "cache_read_input_tokens", 0) or 0
        )

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

    # Log token usage and cost (cache-aware)
    input_cost = total_input_tokens * _INPUT_COST_PER_MTOK / 1_000_000
    output_cost = total_output_tokens * _OUTPUT_COST_PER_MTOK / 1_000_000
    cache_write_cost = total_cache_write_tokens * _CACHE_WRITE_COST_PER_MTOK / 1_000_000
    cache_read_cost = total_cache_read_tokens * _CACHE_READ_COST_PER_MTOK / 1_000_000
    total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost
    parts = [f"input={total_input_tokens} (${input_cost:.4f})"]
    if total_cache_write_tokens or total_cache_read_tokens:
        parts.append(
            f"cache_write={total_cache_write_tokens} (${cache_write_cost:.4f})"
        )
        parts.append(f"cache_read={total_cache_read_tokens} (${cache_read_cost:.4f})")
    parts.append(f"output={total_output_tokens} (${output_cost:.4f})")

    logger.info(
        "LLM usage: %d highlight(s), %d API call(s), %d tool call(s) | %s | total=$%.4f",
        len(highlights),
        api_calls,
        tool_call_count,
        ", ".join(parts),
        total_cost,
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
        highlights=highlights,
        changes=proposed_changes,
        reasoning="".join(reasoning_parts),
        status=changeset_status,
        created_at=datetime.now(timezone.utc).isoformat(),
        routing=routing_info,
        feedback=feedback,
        parent_changeset_id=parent_changeset_id,
    )
    changeset_store.set(changeset)

    return changeset
