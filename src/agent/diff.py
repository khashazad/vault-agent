import difflib


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
