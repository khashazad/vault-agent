import json

from src.models import ReadNoteInput, CreateNoteInput, UpdateNoteInput
from src.vault.reader import read_note
from src.vault.writer import create_note, update_note

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


# Build the full tool definitions list with routing prepended.
def get_tool_definitions() -> list[dict]:
    tools = list(TOOL_DEFINITIONS)
    tools.insert(0, REPORT_ROUTING_DECISION_TOOL)
    return tools


# Dispatch a tool call to the appropriate handler and return the result string.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     tool_name: Name of the tool to execute (read_note, create_note, etc.).
#     tool_input: Tool input parameters parsed from the LLM tool_use block.
#
# Returns:
#     String result to send back as tool_result content.
#
# Raises:
#     ValueError: When tool_name is not recognized.
async def execute_tool(
    vault_path: str, tool_name: str, tool_input: dict
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

    raise ValueError(f"Unknown tool: {tool_name}")
