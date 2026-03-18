from src.models import TagNode, TaxonomyProposal
from src.db import get_migration_store


# Recursively flatten a tag hierarchy into a list of slash-separated paths.
#
# Args:
#     nodes: List of TagNode trees to flatten.
#     prefix: Accumulated parent path prefix.
#
# Returns:
#     Flat list of tag paths (e.g. ["research", "research/ml"]).
def _flatten_tags(nodes: list[TagNode], prefix: str = "") -> list[str]:
    tags: list[str] = []
    for node in nodes:
        full = f"{prefix}/{node.name}" if prefix else node.name
        tags.append(full)
        tags.extend(_flatten_tags(node.children, full))
    return tags


# Read-only registry providing taxonomy lookups for migration prompts.
class VaultRegistry:
    # Initialize registry with a taxonomy proposal.
    #
    # Args:
    #     taxonomy: Active TaxonomyProposal to serve lookups from.
    def __init__(self, taxonomy: TaxonomyProposal):
        self._taxonomy = taxonomy

    # Create a VaultRegistry from the currently active taxonomy in the store.
    #
    # Returns:
    #     VaultRegistry wrapping the active taxonomy, or None if none active.
    @classmethod
    def from_active(cls) -> "VaultRegistry | None":
        taxonomy = get_migration_store().get_active_taxonomy()
        if taxonomy is None:
            return None
        return cls(taxonomy)

    @property
    def taxonomy_id(self) -> str:
        return self._taxonomy.id

    # Return all tags as a flat list of slash-separated paths.
    #
    # Returns:
    #     List of tag paths.
    def get_tag_hierarchy(self) -> list[str]:
        return _flatten_tags(self._taxonomy.tag_hierarchy)

    # Return link targets as dicts with title, aliases, and folder.
    #
    # Returns:
    #     List of link target dicts.
    def get_link_targets(self) -> list[dict[str, str | list[str]]]:
        return [
            {"title": lt.title, "aliases": lt.aliases, "folder": lt.folder}
            for lt in self._taxonomy.link_targets
        ]

    # Return the taxonomy's folder list.
    #
    # Returns:
    #     List of folder path strings.
    def get_folder_structure(self) -> list[str]:
        return list(self._taxonomy.folders)
