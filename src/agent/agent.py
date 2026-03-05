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
from src.agent.tools import get_tool_definitions, execute_tool
from src.agent.prompts import build_system_prompt, build_user_message
from src.agent.diff import generate_diff
from src.vault import validate_path
from src.vault.reader import build_vault_map
from src.vault.writer import compute_create, compute_update
from src.store import changeset_store

logger = logging.getLogger("vault-agent")

MAX_TOOL_CALLS = 15
MODEL = "claude-sonnet-4-5-20250514"


def _init_agent(
    config: AppConfig,
    highlight: HighlightInput,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
):
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    rag_enabled = bool(config.voyage_api_key)
    vault_map = build_vault_map(config.vault_path)
    system_prompt = build_system_prompt(vault_map.as_string, rag_enabled=rag_enabled)
    tool_defs = get_tool_definitions(rag_enabled=rag_enabled)
    messages: list[dict] = [
        {
            "role": "user",
            "content": build_user_message(highlight, feedback, previous_reasoning),
        },
    ]
    return client, system_prompt, tool_defs, messages


async def generate_changeset(
    config: AppConfig,
    highlight: HighlightInput,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    parent_changeset_id: str | None = None,
) -> Changeset:
    """Run the agent to search, decide placement, and generate changes.
    Returns a Changeset with proposed changes (no writes to disk)."""

    client, system_prompt, tool_defs, messages = _init_agent(
        config, highlight, feedback, previous_reasoning
    )

    proposed_changes: list[ProposedChange] = []
    reasoning_parts: list[str] = []
    routing_info: RoutingInfo | None = None
    search_results_count = 0
    tool_call_count = 0

    # Virtual filesystem for files "created" in preview mode
    virtual_fs: dict[str, str] = {}

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
                        )
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

    changeset = Changeset(
        id=str(uuid.uuid4()),
        highlight=highlight,
        changes=proposed_changes,
        reasoning="".join(reasoning_parts),
        created_at=datetime.now(timezone.utc).isoformat(),
        routing=routing_info,
        feedback=feedback,
        parent_changeset_id=parent_changeset_id,
    )
    changeset_store.set(changeset)

    return changeset
