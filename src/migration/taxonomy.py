import json
import re
import uuid
from datetime import datetime, timezone

from src.models import TagNode, LinkTarget, TaxonomyProposal


_TAG_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-/]*$")


def _validate_tag_node(node: TagNode, path: str = "") -> list[str]:
    errors: list[str] = []
    full = f"{path}/{node.name}" if path else node.name
    if not _TAG_NAME_RE.match(node.name):
        errors.append(
            f"Invalid tag name '{full}': must be lowercase alphanumeric with hyphens/slashes"
        )
    for child in node.children:
        errors.extend(_validate_tag_node(child, full))
    return errors


def validate_taxonomy(data: dict) -> list[str]:
    errors: list[str] = []

    if "folders" not in data or not isinstance(data["folders"], list):
        errors.append("Missing or invalid 'folders' field (must be a list)")
    else:
        for f in data["folders"]:
            if not isinstance(f, str) or not f.strip():
                errors.append(f"Invalid folder path: {f!r}")
            elif f.startswith("/") or ".." in f:
                errors.append(f"Folder path must be relative without '..': {f!r}")

    if "tag_hierarchy" not in data or not isinstance(data["tag_hierarchy"], list):
        errors.append("Missing or invalid 'tag_hierarchy' field (must be a list)")
    else:
        for item in data["tag_hierarchy"]:
            try:
                node = TagNode(**item) if isinstance(item, dict) else item
                errors.extend(_validate_tag_node(node))
            except Exception as e:
                errors.append(f"Invalid tag node: {e}")

    if "link_targets" not in data or not isinstance(data["link_targets"], list):
        errors.append("Missing or invalid 'link_targets' field (must be a list)")
    else:
        for lt in data["link_targets"]:
            if isinstance(lt, dict):
                if not lt.get("title"):
                    errors.append("Link target missing 'title'")
                if not lt.get("folder"):
                    errors.append(
                        f"Link target '{lt.get('title', '?')}' missing 'folder'"
                    )
            else:
                errors.append(f"Invalid link target entry: {lt!r}")

    return errors


def import_taxonomy(data: str | dict) -> TaxonomyProposal:
    if isinstance(data, str):
        data = json.loads(data)

    errors = validate_taxonomy(data)
    if errors:
        raise ValueError(f"Taxonomy validation failed: {'; '.join(errors)}")

    tag_hierarchy = [
        TagNode(**t) if isinstance(t, dict) else t for t in data["tag_hierarchy"]
    ]
    link_targets = [
        LinkTarget(**lt) if isinstance(lt, dict) else lt for lt in data["link_targets"]
    ]

    return TaxonomyProposal(
        id=str(uuid.uuid4()),
        folders=data["folders"],
        tag_hierarchy=tag_hierarchy,
        link_targets=link_targets,
        reasoning=data.get("reasoning"),
        status="imported",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
