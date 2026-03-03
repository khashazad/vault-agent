import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import anthropic

from src.models import (
    AgentStreamEvent,
    Changeset,
    CreateNoteInput,
    HighlightInput,
    ProcessResult,
    ProposedChange,
    UpdateNoteInput,
)
from src.config import AppConfig
from src.agent.tools import get_tool_definitions, execute_tool
from src.agent.prompts import build_system_prompt, build_user_message
from src.agent.diff import generate_diff
from src.vault import validate_path
from src.vault.reader import build_vault_map
from src.vault.writer import compute_create, compute_update
from src.store import changeset_store

MAX_TOOL_CALLS = 10
MODEL = "claude-sonnet-4-5-20250514"


def _init_agent(config: AppConfig, highlight: HighlightInput):
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    rag_enabled = bool(config.voyage_api_key)
    vault_map = build_vault_map(config.vault_path)
    system_prompt = build_system_prompt(vault_map.as_string, rag_enabled=rag_enabled)
    tool_defs = get_tool_definitions(rag_enabled=rag_enabled)
    messages: list[dict] = [
        {"role": "user", "content": build_user_message(highlight)},
    ]
    return client, system_prompt, tool_defs, messages


async def process_highlight(
    config: AppConfig, highlight: HighlightInput
) -> ProcessResult:
    client, system_prompt, tool_defs, messages = _init_agent(config, highlight)

    affected_notes: list[str] = []
    reasoning_parts: list[str] = []
    tool_call_count = 0

    while tool_call_count < MAX_TOOL_CALLS:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=tool_defs,
            messages=messages,
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
                if block.type == "tool_use":
                    tool_call_count += 1
                    is_error = False

                    try:
                        result_content = await execute_tool(
                            config.vault_path, block.name, block.input, config=config
                        )

                        if block.name in ("create_note", "update_note"):
                            affected_notes.append(block.input["path"])
                    except Exception as err:
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

    return ProcessResult(
        success=len(affected_notes) > 0 or len(reasoning_parts) > 0,
        action=(
            f"Modified {len(affected_notes)} note(s)"
            if affected_notes
            else "No changes made"
        ),
        affected_notes=affected_notes,
        reasoning="\n\n".join(reasoning_parts),
    )


async def process_highlight_preview(
    config: AppConfig,
    highlight: HighlightInput,
    on_event: Callable[[AgentStreamEvent], Awaitable[None]],
) -> Changeset:
    """Process a highlight in preview mode: stream reasoning, intercept writes,
    return a Changeset with proposed changes instead of writing to disk."""

    client, system_prompt, tool_defs, messages = _init_agent(config, highlight)

    proposed_changes: list[ProposedChange] = []
    reasoning_parts: list[str] = []
    tool_call_count = 0

    # Virtual filesystem for files "created" in preview mode
    # so subsequent reads of those files return the proposed content
    virtual_fs: dict[str, str] = {}

    while tool_call_count < MAX_TOOL_CALLS:
        # Use streaming to get real-time text deltas
        async with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=tool_defs,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        reasoning_parts.append(event.delta.text)
                        await on_event(
                            AgentStreamEvent(
                                type="reasoning",
                                data={"text": event.delta.text},
                            )
                        )

            response = await stream.get_final_message()

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

                await on_event(
                    AgentStreamEvent(
                        type="tool_call",
                        data={"tool_name": tool_name, "input": tool_input},
                    )
                )

                try:
                    if tool_name == "search_vault":
                        result_content = await execute_tool(
                            config.vault_path, tool_name, tool_input, config=config
                        )

                    elif tool_name == "read_note":
                        note_path = tool_input["path"]
                        # Check virtual_fs first (for files "created" in this session)
                        if note_path in virtual_fs:
                            result_content = virtual_fs[note_path]
                        else:
                            result_content = await execute_tool(
                                config.vault_path, tool_name, tool_input, config=config
                            )

                    elif tool_name == "create_note":
                        inp = CreateNoteInput(**tool_input)
                        # Also check virtual_fs — if already "created" in preview, treat as exists
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

                        await on_event(
                            AgentStreamEvent(
                                type="proposed_change",
                                data=change.model_dump(),
                            )
                        )

                        result_content = (
                            f"[Preview] Note would be created at {inp.path}"
                        )

                    elif tool_name == "update_note":
                        inp = UpdateNoteInput(**tool_input)
                        # Read original from virtual_fs or disk
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

                        await on_event(
                            AgentStreamEvent(
                                type="proposed_change",
                                data=change.model_dump(),
                            )
                        )

                        result_content = (
                            f"[Preview] Note would be updated at {inp.path}"
                        )

                    else:
                        raise ValueError(f"Unknown tool: {tool_name}")

                except Exception as err:
                    is_error = True
                    result_content = f"Error: {err}"

                await on_event(
                    AgentStreamEvent(
                        type="tool_result",
                        data={
                            "tool_name": tool_name,
                            "result": result_content,
                            "is_error": is_error,
                        },
                    )
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

    changeset = Changeset(
        id=str(uuid.uuid4()),
        highlight=highlight,
        changes=proposed_changes,
        reasoning="".join(reasoning_parts),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    changeset_store.set(changeset)

    await on_event(
        AgentStreamEvent(
            type="complete",
            data={"changeset_id": changeset.id, "change_count": len(proposed_changes)},
        )
    )

    return changeset
