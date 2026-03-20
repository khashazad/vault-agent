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
from src.db import get_migration_store
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
_NO_CHANGES = "NO_CHANGES_NEEDED"


# Check if LLM response is the NO_CHANGES_NEEDED shortcut.
def _is_no_changes(content: str) -> bool:
    return content.strip().startswith(_NO_CHANGES)


# Extract the MIGRATION_META HTML comment block from LLM output.
#
# Parses target_folder and new_link_targets from the metadata block,
# then returns the content with the block stripped.
#
# Args:
#     content: Raw LLM output containing the MIGRATION_META block.
#
# Returns:
#     Tuple of (clean_content, target_folder, new_link_targets).
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


# Scan the vault and estimate total LLM cost for migrating all notes.
#
# Uses a rough 4-chars-per-token heuristic and accounts for prompt
# caching (first call pays cache_write, subsequent calls pay cache_read).
# When taxonomy_id is provided, builds the actual system prompt to get
# a more accurate system token estimate.
#
# Args:
#     vault_path: Absolute path to the source vault.
#     model: Model key from MODELS pricing dict.
#     taxonomy_id: Optional taxonomy ID for accurate system prompt sizing.
#
# Returns:
#     CostEstimate with note count, token estimates, and USD cost.
def estimate_cost(
    vault_path: str,
    model: str = DEFAULT_MODEL,
    taxonomy_id: str | None = None,
) -> CostEstimate:
    total_chars = 0
    total_notes = 0

    for _, file_path in iter_markdown_files(vault_path):
        total_notes += 1
        full = Path(vault_path) / file_path
        total_chars += len(full.read_text(encoding="utf-8"))

    est_input = total_chars // _CHARS_PER_TOKEN
    # Rough: output ~80% of input
    est_output = int(est_input * 0.8)
    pricing = MODELS[model]

    # Estimate system prompt tokens from actual taxonomy if available
    system_tokens = 2000
    if taxonomy_id:
        store = get_migration_store()
        taxonomy = store.get_taxonomy(taxonomy_id)
        if taxonomy:
            system, _ = build_migration_prompt(taxonomy, "", "")
            system_tokens = len(system) // _CHARS_PER_TOKEN

    # First call pays cache_write, rest pay cache_read for system prompt
    cache_write_cost = system_tokens * pricing["cache_write"] / 1_000_000
    cache_read_cost = (
        system_tokens * max(total_notes - 1, 0) * pricing["cache_read"] / 1_000_000
    )
    input_cost = est_input * pricing["input"] / 1_000_000
    output_cost = est_output * pricing["output"] / 1_000_000
    total_cost = cache_write_cost + cache_read_cost + input_cost + output_cost
    batch_cost = total_cost * 0.5

    return CostEstimate(
        total_notes=total_notes,
        total_chars=total_chars,
        estimated_input_tokens=est_input,
        estimated_output_tokens=est_output,
        estimated_system_tokens=system_tokens,
        estimated_cost_usd=round(total_cost, 4),
        batch_estimated_cost_usd=round(batch_cost, 4),
        model=model,
    )


# Migrate a single note via LLM using the taxonomy-driven prompt.
#
# Sends the note through Claude with the migration prompt, parses the
# response for target folder and cleaned content, generates a diff,
# and records token usage.
#
# Args:
#     config: App config with API key.
#     note: MigrationNote with original content.
#     taxonomy: Active taxonomy for prompt construction.
#     model: Model key from MODELS pricing dict.
#
# Returns:
#     Updated MigrationNote with proposed_content, diff, and usage.
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


# Run background migration of all pending notes in a job.
#
# Processes notes concurrently (up to _CONCURRENCY), updates each note's
# status in the store, and aggregates token usage on the job.
#
# Args:
#     config: App config with API key.
#     job_id: Migration job identifier.
#     model: Model key from MODELS pricing dict.
#     note_paths: Optional subset of paths to migrate (None = all pending).
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

    try:
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
                        total_usage.cache_write_tokens += (
                            result.usage.cache_write_tokens
                        )
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
    except Exception:
        logger.exception("Migration job %s failed", job_id)
        job = store.get_job(job_id)
        if job:
            job.status = "failed"
            store.set_job(job)


# Scan the source vault and create a migration job with one note row per file.
#
# Creates the target vault directory and persists the job and all note
# records to the migration store.
#
# Args:
#     source_vault: Absolute path to the source Obsidian vault.
#     target_vault: Absolute path for the migrated output vault.
#     taxonomy_id: Optional taxonomy ID to associate with the job.
#
# Returns:
#     New MigrationJob with status 'pending'.
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


# Resume a failed migration job by resetting stuck notes and re-running.
#
# Args:
#     config: App config with API key.
#     job_id: Migration job identifier.
#     model: Model key from MODELS pricing dict.
async def resume_migration(
    config: AppConfig,
    job_id: str,
    model: str = DEFAULT_MODEL,
) -> None:
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        logger.error("Migration job %s not found", job_id)
        return

    if job.status != "failed":
        logger.error("Cannot resume job %s with status %s", job_id, job.status)
        return

    # Reset any notes stuck in 'processing' back to 'pending'
    reset_count = store.reset_stuck_notes(job_id)
    if reset_count:
        logger.info("Reset %d stuck notes for job %s", reset_count, job_id)

    # Recalculate processed_notes from non-pending/processing notes
    all_notes, _ = store.get_notes_by_job(job_id, limit=10000)
    processed = sum(1 for n in all_notes if n.status not in ("pending", "processing"))
    job.processed_notes = processed
    store.set_job(job)

    await run_migration(config, job_id, model)


# Submit all pending notes in a migration job to the Anthropic Batch API.
#
# Builds one batch request per note using the shared taxonomy prompt,
# sets the job to batch mode, and returns the batch ID for polling.
#
# Args:
#     config: App config with API key.
#     job_id: Migration job identifier.
#     model: Model key from MODELS pricing dict.
#
# Returns:
#     Batch ID string for polling.
async def submit_migration_batch(
    config: AppConfig,
    job_id: str,
    model: str = DEFAULT_MODEL,
) -> str:
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job:
        raise ValueError(f"Migration job {job_id} not found")

    taxonomy = store.get_taxonomy(job.taxonomy_id) if job.taxonomy_id else None
    if not taxonomy:
        raise ValueError(f"No taxonomy found for job {job_id}")

    notes, _ = store.get_notes_by_job(job_id, status="pending", limit=10000)
    if not notes:
        raise ValueError(f"No pending notes in job {job_id}")

    # Build batch requests — one per note, shared system prompt
    requests = []
    for note in notes:
        system, user = build_migration_prompt(
            taxonomy, note.original_content, note.source_path
        )
        requests.append(
            {
                "custom_id": note.id,
                "params": {
                    "model": MODELS[model]["id"],
                    "max_tokens": _MIGRATION_MAX_TOKENS,
                    "system": [
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": user}],
                },
            }
        )

    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    batch = await client.messages.batches.create(requests=requests)

    job.batch_id = batch.id
    job.batch_mode = True
    job.status = "migrating"
    store.set_job(job)

    logger.info(
        "Migration batch submitted: job=%s batch=%s notes=%d",
        job_id,
        batch.id,
        len(notes),
    )
    return batch.id


# Poll a migration batch and process results when complete.
#
# Checks batch status via the Anthropic API. When ended, iterates
# results and updates each note: parses MIGRATION_META, detects
# NO_CHANGES_NEEDED shortcut (auto-approves), generates diffs, and
# records usage with batch discount.
#
# Args:
#     config: App config with API key.
#     job_id: Migration job identifier.
#
# Returns:
#     Batch processing status string.
async def poll_migration_batch(
    config: AppConfig,
    job_id: str,
) -> str:
    store = get_migration_store()
    job = store.get_job(job_id)
    if not job or not job.batch_id:
        raise ValueError(f"No batch ID for job {job_id}")

    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    batch = await client.messages.batches.retrieve(job.batch_id)

    if batch.processing_status != "ended":
        # Update progress from request_counts
        counts = batch.request_counts
        job.processed_notes = (
            counts.succeeded + counts.errored + counts.expired + counts.canceled
        )
        store.set_job(job)
        return batch.processing_status

    # Batch ended — process all results
    total_usage = TokenUsage(
        input_tokens=0,
        output_tokens=0,
        cache_write_tokens=0,
        cache_read_tokens=0,
        api_calls=0,
        tool_calls=0,
        total_cost_usd=0.0,
    )

    async for result in await client.messages.batches.results(job.batch_id):
        note = store.get_note(result.custom_id)
        if not note:
            continue

        if result.result.type == "succeeded":
            msg = result.result.message
            raw_output = msg.content[0].text

            if _is_no_changes(raw_output):
                # Already compliant — auto-approve with original content
                _, target_folder, _ = _parse_migration_meta(raw_output)
                if target_folder:
                    filename = Path(note.source_path).name
                    note.target_path = f"{target_folder}/{filename}"
                note.no_changes = True
                note.proposed_content = note.original_content
                note.diff = ""
                note.status = "approved"
            else:
                clean_content, target_folder, _ = _parse_migration_meta(raw_output)
                if target_folder:
                    filename = Path(note.source_path).name
                    note.target_path = f"{target_folder}/{filename}"
                note.proposed_content = clean_content
                note.diff = generate_diff(
                    note.source_path, note.original_content, clean_content
                )
                note.status = "proposed"

            inp, out, cw, cr = extract_usage(msg)
            # Reverse-lookup model key from model ID
            model_key = next(
                (k for k, v in MODELS.items() if v["id"] == msg.model),
                DEFAULT_MODEL,
            )
            note.usage = build_token_usage(
                inp,
                out,
                cw,
                cr,
                api_calls=1,
                tool_calls=0,
                model_key=model_key,
                is_batch=True,
            )
            total_usage.input_tokens += inp
            total_usage.output_tokens += out
            total_usage.cache_write_tokens += cw
            total_usage.cache_read_tokens += cr
            total_usage.api_calls += 1
            total_usage.total_cost_usd += note.usage.total_cost_usd
        else:
            # errored / expired / canceled
            note.status = "failed"
            note.error = f"Batch result: {result.result.type}"

        store.update_note(job_id, note)

    job.processed_notes = job.total_notes
    job.total_usage = total_usage
    job.estimated_cost_usd = total_usage.total_cost_usd
    job.status = "review"
    store.set_job(job)

    logger.info(
        "Migration batch complete: job=%s notes=%d cost=$%.4f",
        job_id,
        job.total_notes,
        total_usage.total_cost_usd,
    )
    return "ended"
