import logging
from dataclasses import dataclass, field

from pyzotero import zotero

logger = logging.getLogger("vault-agent")


@dataclass
class ZoteroCollectionInfo:
    key: str
    name: str
    parent_collection: str | None
    num_items: int
    num_collections: int


@dataclass
class ZoteroAnnotation:
    key: str
    text: str
    comment: str
    color: str
    page_label: str
    annotation_type: str
    date_added: str
    parent_key: str


@dataclass
class ZoteroPaperMetadata:
    key: str
    title: str
    authors: list[str]
    doi: str
    abstract: str
    publication_title: str
    year: str
    item_type: str
    url: str


@dataclass
class ZoteroPaper:
    metadata: ZoteroPaperMetadata
    annotations: list[ZoteroAnnotation] = field(default_factory=list)


def _extract_collection(item: dict) -> ZoteroCollectionInfo:
    """Extract collection info from a Zotero collection item."""
    data = item.get("data", item)
    meta = item.get("meta", {})
    parent = data.get("parentCollection", False)
    return ZoteroCollectionInfo(
        key=data.get("key", item.get("key", "")),
        name=data.get("name", ""),
        parent_collection=parent or None,
        num_items=meta.get("numItems", 0),
        num_collections=meta.get("numCollections", 0),
    )


def _format_creators(creators: list[dict]) -> list[str]:
    """Format Zotero creator dicts into 'Last, First' strings."""
    names = []
    for c in creators:
        last = c.get("lastName", "")
        first = c.get("firstName", "")
        if last and first:
            names.append(f"{last}, {first}")
        elif c.get("name"):
            names.append(c["name"])
        elif last:
            names.append(last)
    return names


def _extract_paper_metadata(item_data: dict, item_key: str) -> ZoteroPaperMetadata:
    """Extract paper metadata from a Zotero bibliographic item."""
    data = item_data.get("data", item_data)
    return ZoteroPaperMetadata(
        key=item_key,
        title=data.get("title", ""),
        authors=_format_creators(data.get("creators", [])),
        doi=data.get("DOI", ""),
        abstract=data.get("abstractNote", ""),
        publication_title=data.get("publicationTitle", ""),
        year=data.get("date", "")[:4] if data.get("date") else "",
        item_type=data.get("itemType", ""),
        url=data.get("url", ""),
    )


def _extract_annotation(item_data: dict) -> ZoteroAnnotation:
    """Extract annotation fields from a Zotero annotation item."""
    data = item_data.get("data", item_data)
    return ZoteroAnnotation(
        key=data.get("key", ""),
        text=data.get("annotationText", ""),
        comment=data.get("annotationComment", ""),
        color=data.get("annotationColor", ""),
        page_label=data.get("annotationPageLabel", ""),
        annotation_type=data.get("annotationType", ""),
        date_added=data.get("dateAdded", ""),
        parent_key=data.get("parentItem", ""),
    )


class ZoteroClient:
    def __init__(self, library_id: str, library_type: str, api_key: str):
        self._zot = zotero.Zotero(library_id, library_type, api_key)

    def fetch_collections(self) -> list[ZoteroCollectionInfo]:
        """Fetch all collections in the library."""
        raw = self._zot.collections()
        return [_extract_collection(item) for item in raw]

    def fetch_annotations(
        self, since: int | None = None, collection_key: str | None = None
    ) -> list[dict]:
        """Fetch annotation items, optionally filtered by version and collection."""
        params: dict = {"itemType": "annotation"}
        if since is not None:
            params["since"] = since
        if collection_key:
            return self._zot.collection_items(collection_key, **params)
        return self._zot.items(**params)

    def fetch_item(self, item_key: str) -> dict:
        """Fetch a single item by key."""
        return self._zot.item(item_key)

    @property
    def last_modified_version(self) -> int:
        """Return the library version from the last API response."""
        return int(self._zot.request.headers.get("Last-Modified-Version", 0))

    def fetch_annotations_grouped(
        self, since: int | None = None, collection_key: str | None = None
    ) -> list[ZoteroPaper]:
        """Fetch annotations and group them by parent paper.

        Resolution chain: annotation → PDF attachment → bibliographic item.
        """
        raw_annotations = self.fetch_annotations(since, collection_key)
        if not raw_annotations:
            return []

        # Group annotations by parent attachment key
        attachment_groups: dict[str, list[ZoteroAnnotation]] = {}
        for item in raw_annotations:
            ann = _extract_annotation(item)
            # Skip annotations without highlight text
            if not ann.text and not ann.comment:
                continue
            attachment_groups.setdefault(ann.parent_key, []).append(ann)

        # Resolve attachment → paper (two-hop)
        paper_map: dict[str, ZoteroPaper] = {}  # paper_key → ZoteroPaper
        attachment_to_paper: dict[str, str] = {}  # attachment_key → paper_key

        for attachment_key in attachment_groups:
            if attachment_key in attachment_to_paper:
                continue
            try:
                attachment = self.fetch_item(attachment_key)
                attachment_data = attachment.get("data", attachment)
                paper_key = attachment_data.get("parentItem", "")
                if not paper_key:
                    logger.warning(
                        "Attachment %s has no parent item, skipping", attachment_key
                    )
                    continue
                attachment_to_paper[attachment_key] = paper_key

                if paper_key not in paper_map:
                    paper_item = self.fetch_item(paper_key)
                    metadata = _extract_paper_metadata(paper_item, paper_key)
                    paper_map[paper_key] = ZoteroPaper(metadata=metadata)
            except Exception as e:
                logger.warning("Failed to resolve attachment %s: %s", attachment_key, e)
                continue

        # Assign annotations to papers
        for attachment_key, annotations in attachment_groups.items():
            paper_key = attachment_to_paper.get(attachment_key)
            if paper_key and paper_key in paper_map:
                paper_map[paper_key].annotations.extend(annotations)

        # Sort annotations within each paper by page label then date
        for paper in paper_map.values():
            paper.annotations.sort(
                key=lambda a: (a.page_label or "", a.date_added or "")
            )

        return list(paper_map.values())

    def fetch_papers(
        self, collection_key: str | None = None
    ) -> list[ZoteroPaperMetadata]:
        """Fetch all top-level bibliographic items (no attachments/annotations/notes)."""
        if collection_key:
            items = self._zot.everything(self._zot.collection_items_top(collection_key))
        else:
            items = self._zot.everything(self._zot.top())
        # top() already excludes child items (attachments/annotations);
        # filter out standalone notes client-side
        skip = {"note", "attachment", "annotation"}
        return [
            _extract_paper_metadata(item, item["key"])
            for item in items
            if item.get("data", {}).get("itemType", "") not in skip
        ]

    def fetch_paper_annotations(self, paper_key: str) -> list[ZoteroAnnotation]:
        """Fetch annotations for a single paper via attachment children."""
        children = self._zot.children(paper_key)
        annotations: list[ZoteroAnnotation] = []
        for child in children:
            data = child.get("data", child)
            if data.get("itemType") != "attachment":
                continue
            attachment_key = child.get("key", data.get("key", ""))
            if not attachment_key:
                continue
            ann_items = self._zot.children(attachment_key, itemType="annotation")
            for ann_item in ann_items:
                ann = _extract_annotation(ann_item)
                if ann.text or ann.comment:
                    annotations.append(ann)
        annotations.sort(key=lambda a: (a.page_label or "", a.date_added or ""))
        return annotations

    def count_annotations_per_paper(self) -> dict[str, int]:
        """Count annotations per paper via bulk fetch (2 paginated API calls)."""
        all_annotations = self._zot.everything(self._zot.items(itemType="annotation"))

        # Group annotation counts by parent attachment
        att_counts: dict[str, int] = {}
        for ann in all_annotations:
            data = ann.get("data", {})
            parent = data.get("parentItem", "")
            if parent and (data.get("annotationText") or data.get("annotationComment")):
                att_counts[parent] = att_counts.get(parent, 0) + 1

        if not att_counts:
            return {}

        # Resolve attachment → paper
        all_attachments = self._zot.everything(self._zot.items(itemType="attachment"))
        att_to_paper: dict[str, str] = {}
        for att in all_attachments:
            key = att.get("key", att.get("data", {}).get("key", ""))
            parent = att.get("data", {}).get("parentItem", "")
            if key and parent:
                att_to_paper[key] = parent

        # Aggregate by paper
        paper_counts: dict[str, int] = {}
        for att_key, count in att_counts.items():
            paper_key = att_to_paper.get(att_key)
            if paper_key:
                paper_counts[paper_key] = paper_counts.get(paper_key, 0) + count

        return paper_counts
