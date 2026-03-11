import difflib


# Produce a unified diff between original and proposed file contents.
#
# Args:
#     path: Relative file path used in the diff header (a/path, b/path).
#     original: Original file content.
#     proposed: Proposed file content.
#
# Returns:
#     Unified diff string, or empty string if contents are identical.
def generate_diff(path: str, original: str, proposed: str) -> str:
    original_lines = original.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        proposed_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff)
