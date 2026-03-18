import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from src.config import AppConfig
from src.models import (
    CostEstimate,
    MigrationJob,
    MigrationNote,
    TaxonomyProposal,
    TokenUsage,
)
from src.agent.utils import (
    MODELS,
    DEFAULT_MODEL,
    build_token_usage,
    create_with_retry,
    extract_usage,
)
from src.agent.diff import generate_diff
from src.migration.prompts import build_migration_prompt
from src.store import get_migration_store
from src.vault import iter_markdown_files

logger = logging.getLogger("vault-agent")

_MIGRATION_MAX_TOKENS = 16384
_META_RE = re.compile(
    r"<!--\s*MIGRATION_META\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)
_CONCURRENCY = 5
# ~4 chars per token is a rough estimate for English text
_CHARS_PER_TOKEN = 4


def _parse_migration_meta(content: str) -> tuple[str, str | None, list[str]]:
    match = _META_RE.search(content)
    if not match:
        return content, None, []

    clean_content = content[: match.start()].rstrip()
    meta_block = match.group(1)

    target_folder = None
    new_link_targets: list[str] = []

    for line in meta_block.strip().splitlines():
        line = line.strip()
        if line.startswith("target_folder:"):
            target_folder = line.split(":", 1)[1].strip()
        elif line.startswith("new_link_targets:"):
            raw = line.split(":", 1)[1].strip()
            if raw.lower() != "none" and raw:
                new_link_targets = [t.strip() for t in raw.split(",") if t.strip()]

    return clean_content, target_folder, new_link_targets


def estimate_cost(vault_path: str, model: str = DEFAULT_MODEL) -> CostEstimate:
    total_chars = 0
    total_notes = 0

    for _, file_path in iter_markdown_files(vault_path):
        total_notes += 1
        full = Path(vault_path) / file_path
        total_chars += len(full.read_text(encoding="utf-8"))

    est_input = total_chars // _CHARS_PER_TOKEN
    # Rough: system prompt ~2k tokens shared (cached after first), output ~80% of input
    est_output = int(est_input * 0.8)
    pricing = MODELS[model]
    # First call pays cache_write, rest pay cache_read for system prompt
    system_tokens = 2000
    cache_write_cost = system_tokens * pricing["cache_write"] / 1_000_000
    cache_read_cost = (
        system_tokens * (total_notes - 1) * pricing["cache_read"] / 1_000_000
    )
    input_cost = est_input * pricing["input"] / 1_000_000
    output_cost = est_output * pricing["output"] / 1_000_000
    total_cost = cache_write_cost + cache_read_cost + input_cost + output_cost

    return CostEstimate(
        total_notes=total_notes,
        total_chars=total_chars,
        estimated_input_tokens=est_input,
        estimated_output_tokens=est_output,
        estimated_cost_usd=round(total_cost, 4),
        model=model,
    )


async def migrate_note(
    config: AppConfig,
    note: MigrationNote,
    taxonomy: TaxonomyProposal,
    model: str = DEFAULT_MODEL,
) -> MigrationNote:
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    system, user = build_migration_prompt(
        taxonomy, note.original_content, note.source_path
    )

    response = await create_with_retry(
        client,
        model=MODELS[model]["id"],
        max_tokens=_MIGRATION_MAX_TOKENS,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        messages=[{"role": "user", "content": user}],
    )

    raw_output = response.content[0].text
    clean_content, target_folder, _ = _parse_migration_meta(raw_output)

    if target_folder:
        filename = Path(note.source_path).name
        note.target_path = f"{target_folder}/{filename}"

    note.proposed_content = clean_content
    note.diff = generate_diff(note.source_path, note.original_content, clean_content)
    note.status = "proposed"

    inp, out, cw, cr = extract_usage(response)
    note.usage = build_token_usage(
        inp, out, cw, cr, api_calls=1, tool_calls=0, model_key=model
    )

    return note


async def run_migration(
    config: AppConfig,
    job_id: str,
    model: str = DEFAULT_MODEL,
    note_paths: list[str] | None = None,
) -> None:
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        logger.error("Migration job %s not found", job_id)
        return

    taxonomy = store.get_taxonomy(job.taxonomy_id) if job.taxonomy_id else None
    if not taxonomy:
        job.status = "failed"
        store.set_job(job)
        logger.error("No taxonomy found for job %s", job_id)
        return

    job.status = "migrating"
    store.set_job(job)

    semaphore = asyncio.Semaphore(_CONCURRENCY)
    total_usage = TokenUsage(
        input_tokens=0,
        output_tokens=0,
        cache_write_tokens=0,
        cache_read_tokens=0,
        api_calls=0,
        tool_calls=0,
        total_cost_usd=0.0,
    )

    async def _process(note: MigrationNote) -> None:
        async with semaphore:
            try:
                note.status = "processing"
                store.update_note(job_id, note)

                result = await migrate_note(config, note, taxonomy, model)
                store.update_note(job_id, result)

                if result.usage:
                    total_usage.input_tokens += result.usage.input_tokens
                    total_usage.output_tokens += result.usage.output_tokens
                    total_usage.cache_write_tokens += result.usage.cache_write_tokens
                    total_usage.cache_read_tokens += result.usage.cache_read_tokens
                    total_usage.api_calls += result.usage.api_calls
                    total_usage.total_cost_usd += result.usage.total_cost_usd

                store.increment_processed(job_id)
            except Exception as e:
                logger.exception("Failed to migrate note %s", note.source_path)
                note.status = "failed"
                note.error = str(e)
                store.update_note(job_id, note)
                store.increment_processed(job_id)

    # Get pending notes, optionally filtered by path
    notes, _ = store.get_notes_by_job(job_id, status="pending", limit=10000)
    if note_paths:
        path_set = set(note_paths)
        notes = [n for n in notes if n.source_path in path_set]

    tasks = [asyncio.create_task(_process(n)) for n in notes]
    await asyncio.gather(*tasks)

    # Update job with totals
    job = store.get_job(job_id)
    if job:
        job.total_usage = total_usage
        job.estimated_cost_usd = total_usage.total_cost_usd
        job.status = "review"
        store.set_job(job)

    logger.info(
        "Migration job %s complete: %d notes, $%.4f",
        job_id,
        len(notes),
        total_usage.total_cost_usd,
    )


def create_migration_job(
    source_vault: str,
    target_vault: str,
    taxonomy_id: str | None = None,
) -> MigrationJob:
    store = get_migration_store()
    job_id = str(uuid.uuid4())

    # Scan source vault for notes
    note_count = 0
    for md_file, file_path in iter_markdown_files(source_vault):
        content = md_file.read_text(encoding="utf-8")
        note = MigrationNote(
            id=str(uuid.uuid4()),
            source_path=file_path,
            target_path=file_path,  # default: same path, LLM may reassign
            original_content=content,
        )
        store.set_note(job_id, note)
        note_count += 1

    job = MigrationJob(
        id=job_id,
        source_vault=source_vault,
        target_vault=target_vault,
        taxonomy_id=taxonomy_id,
        status="pending",
        total_notes=note_count,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.set_job(job)

    # Create target vault dir
    Path(target_vault).mkdir(parents=True, exist_ok=True)

    return job
