from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import AppConfig

from src.models import ReadNoteInput, CreateNoteInput, UpdateNoteInput
from src.vault.reader import read_note
from src.vault.writer import create_note, update_note
from src.rag.search import search_vault

MAX_SEARCH_RESULTS = 20

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_note",
        "description": (
            "Read the full content of a note in the vault. Use this to inspect a note "
            "before deciding to modify it. Always read a note before updating it. "
            "The path is relative to the vault root, e.g. 'Projects/My Project.md'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path to the note from the vault root, "
                        "e.g. 'Projects/My Project.md'"
                    ),
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_note",
        "description": (
            "Create a new note in the vault. Must not overwrite an existing file. "
            "Include proper YAML frontmatter. The content should be complete markdown "
            "including the --- frontmatter delimiters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path for the new note, e.g. 'References/Article Title.md'",
                },
                "content": {
                    "type": "string",
                    "description": "Full markdown content including YAML frontmatter",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "update_note",
        "description": (
            "Update an existing note. 'append_section' adds content under a heading "
            "(or at end if heading not found). "
            "You must read the note first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the existing note",
                },
                "operation": {
                    "type": "string",
                    "enum": ["append_section"],
                    "description": "The type of update to perform",
                },
                "heading": {
                    "type": "string",
                    "description": (
                        "For append_section: the heading to append under. "
                        "If omitted, appends to end."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "For append_section: the markdown content to append",
                },
            },
            "required": ["path", "operation"],
        },
    },
]

SEARCH_VAULT_TOOL = {
    "name": "search_vault",
    "description": (
        "Semantic search across the vault's note contents. Returns the most relevant "
        "note sections ranked by similarity to the query. Use this BEFORE reading notes "
        "to find which notes are most relevant to the content topic."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query describing the topic to find",
            },
            "n": {
                "type": "integer",
                "description": "Number of results to return (default 10, max 20)",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}

REPORT_ROUTING_DECISION_TOOL = {
    "name": "report_routing_decision",
    "description": (
        "Report your placement decision BEFORE making any changes. Call this exactly "
        "once after searching and reading candidate notes. This declares where you will "
        "place the content and why. It does not modify any notes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["update", "create", "skip"],
                "description": "Whether to update an existing note, create a new one, or skip (info already in vault)",
            },
            "duplicate_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "When action='skip': paths of existing notes that already contain this information.",
            },
            "target_path": {
                "type": "string",
                "description": (
                    "Path of the existing note to update (required when action='update'), "
                    "or suggested path for a new note (optional when action='create')"
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this placement was chosen",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score from 0.0 to 1.0",
            },
        },
        "required": ["action", "reasoning", "confidence"],
    },
}


def format_search_results(results) -> str:
    """Format search results into a readable string for the LLM context."""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"### Result {i} (score: {r.score:.4f})")
        lines.append(f"**Note:** `{r.note_path}` > {r.heading}")
        lines.append(r.content[:200])
        lines.append("")
    return "\n".join(lines)


def get_tool_definitions() -> list[dict]:
    tools = list(TOOL_DEFINITIONS)
    tools.insert(0, REPORT_ROUTING_DECISION_TOOL)
    tools.insert(0, SEARCH_VAULT_TOOL)
    return tools


async def execute_tool(
    vault_path: str, tool_name: str, tool_input: dict, config: AppConfig | None = None
) -> str:
    if tool_name == "read_note":
        inp = ReadNoteInput(**tool_input)
        note = read_note(vault_path, inp.path)
        fm_lines = "\n".join(
            f"{k}: {json.dumps(v)}" for k, v in note.frontmatter.items()
        )
        return f"---\n{fm_lines}\n---\n{note.content}"

    if tool_name == "create_note":
        inp = CreateNoteInput(**tool_input)
        return create_note(vault_path, inp)

    if tool_name == "update_note":
        inp = UpdateNoteInput(**tool_input)
        return update_note(vault_path, inp)

    if tool_name == "search_vault":
        query = tool_input.get("query", "")
        n = min(tool_input.get("n", 7), MAX_SEARCH_RESULTS)
        results = await search_vault(
            query, config.voyage_api_key, config.lancedb_path, n=n
        )
        if not results:
            return "No results found."
        return format_search_results(results)

    raise ValueError(f"Unknown tool: {tool_name}")
