import hashlib
import re
from dataclasses import dataclass

from src.vault.reader import HEADING_RE

IMAGE_EMBED_RE = re.compile(r"!\[\[.*?\]\]|!\[.*?\]\(.*?\)")
LATEX_BLOCK_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

MIN_CHUNK_CHARS = 50


@dataclass
class Chunk:
    note_path: str
    heading: str
    content: str
    content_hash: str


def _clean_content(text: str) -> str:
    text = CODE_FENCE_RE.sub("", text)
    text = LATEX_BLOCK_RE.sub("", text)
    text = IMAGE_EMBED_RE.sub("", text)
    return text


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def chunk_note(note_path: str, title: str, content: str) -> list[Chunk]:
    cleaned = _clean_content(content)
    matches = list(HEADING_RE.finditer(cleaned))

    if not matches:
        text = cleaned.strip()
        if len(text) < MIN_CHUNK_CHARS:
            return []
        return [Chunk(note_path, f"# {title}", text, _md5(text))]

    chunks: list[Chunk] = []
    heading_counts: dict[str, int] = {}

    # Preamble before first heading
    preamble = cleaned[: matches[0].start()].strip()
    if len(preamble) >= MIN_CHUNK_CHARS:
        chunks.append(Chunk(note_path, f"# {title}", preamble, _md5(preamble)))

    for i, match in enumerate(matches):
        heading_text = match.group(2).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body = cleaned[match.end() : end].strip()

        if len(body) < MIN_CHUNK_CHARS:
            continue

        # Handle duplicate headings within a note
        if heading_text in heading_counts:
            heading_counts[heading_text] += 1
            heading_key = f"{heading_text} ({heading_counts[heading_text]})"
        else:
            heading_counts[heading_text] = 1
            heading_key = heading_text

        chunks.append(Chunk(note_path, heading_key, body, _md5(body)))

    return chunks
