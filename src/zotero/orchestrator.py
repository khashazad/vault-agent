import logging

from src.config import AppConfig
from src.models import (
    ContentItem,
    SourceMetadata,
    ZoteroSyncRequest,
    ZoteroSyncResponse,
)
from src.zotero.client import ZoteroClient, ZoteroPaper
from src.zotero.sync import ZoteroSyncState
from src.agent.agent import generate_changeset

logger = logging.getLogger("vault-agent")


def _format_source(paper: ZoteroPaper) -> str:
    """Format paper metadata into a citation-style source string."""
    meta = paper.metadata
    authors = meta.authors
    if not authors:
        author_str = "Unknown"
    elif len(authors) == 1:
        author_str = authors[0].split(",")[0]  # Last name only
    else:
        author_str = f"{authors[0].split(',')[0]} et al."

    title = meta.title or "Untitled"
    year = meta.year or "n.d."
    return f"{author_str} - {title} ({year})"


def _build_source_metadata(paper: ZoteroPaper) -> SourceMetadata:
    """Build SourceMetadata from a ZoteroPaper's metadata."""
    meta = paper.metadata
    return SourceMetadata(
        title=meta.title,
        doi=getattr(meta, "doi", None),
        authors=meta.authors,
        year=meta.year,
        publication_title=getattr(meta, "publication_title", None),
        abstract=getattr(meta, "abstract", None),
        paper_key=meta.key,
        url=getattr(meta, "url", None),
    )


def _paper_to_content_items(paper: ZoteroPaper) -> list[ContentItem]:
    """Convert a ZoteroPaper's annotations into ContentItem objects."""
    source = _format_source(paper)
    source_meta = _build_source_metadata(paper)
    items = []
    for ann in paper.annotations:
        text = ann.text or ""
        if not text and not ann.comment:
            continue

        # Build annotation field from comment + page label
        parts = []
        if ann.comment:
            parts.append(ann.comment)
        if ann.page_label:
            parts.append(f"[p. {ann.page_label}]")
        annotation = " ".join(parts) if parts else None

        items.append(
            ContentItem(
                text=text or ann.comment,
                source=source,
                annotation=annotation if text else None,
                source_type="zotero",
                color=ann.color or None,
                source_metadata=source_meta,
            )
        )
    return items


async def sync_zotero(
    config: AppConfig, request: ZoteroSyncRequest | None = None
) -> ZoteroSyncResponse:
    """Fetch Zotero annotations and run each paper through the agent pipeline."""
    if not config.zotero_api_key or not config.zotero_library_id:
        raise ValueError("Zotero API key and library ID must be configured")

    if request is None:
        request = ZoteroSyncRequest()

    client = ZoteroClient(
        library_id=config.zotero_library_id,
        library_type=config.zotero_library_type,
        api_key=config.zotero_api_key,
    )
    sync_state = ZoteroSyncState()

    # Determine since version
    since = None
    if not request.full_sync:
        since = sync_state.get_last_version()

    logger.info(
        "Starting Zotero sync (since=%s, collection=%s, full=%s)",
        since,
        request.collection_key,
        request.full_sync,
    )

    papers = client.fetch_annotations_grouped(since, request.collection_key)
    library_version = client.last_modified_version

    # Filter by paper_keys if provided
    if request.paper_keys:
        paper_key_set = set(request.paper_keys)
        papers = [p for p in papers if p.metadata.key in paper_key_set]

    logger.info("Found %d papers with annotations", len(papers))

    changeset_ids: list[str] = []
    skipped_papers: list[str] = []

    for paper in papers:
        items = _paper_to_content_items(paper)
        if not items:
            skipped_papers.append(
                f"{paper.metadata.title or paper.metadata.key} (no annotations)"
            )
            continue

        try:
            changeset = await generate_changeset(
                config,
                items=items,
            )
            changeset_ids.append(changeset.id)
            logger.info(
                "Generated changeset %s for paper '%s' (%d items)",
                changeset.id,
                paper.metadata.title,
                len(items),
            )
        except Exception as e:
            logger.error("Failed to process paper '%s': %s", paper.metadata.title, e)
            skipped_papers.append(
                f"{paper.metadata.title or paper.metadata.key} (error: {e})"
            )

    # Record new library version
    sync_state.set_last_version(library_version)

    return ZoteroSyncResponse(
        papers_found=len(papers),
        papers_processed=len(changeset_ids),
        changeset_ids=changeset_ids,
        skipped_papers=skipped_papers,
        library_version=library_version,
    )
