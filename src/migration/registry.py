from src.models import TagNode, TaxonomyProposal
from src.store import get_migration_store


def _flatten_tags(nodes: list[TagNode], prefix: str = "") -> list[str]:
    tags: list[str] = []
    for node in nodes:
        full = f"{prefix}/{node.name}" if prefix else node.name
        tags.append(full)
        tags.extend(_flatten_tags(node.children, full))
    return tags


class VaultRegistry:
    def __init__(self, taxonomy: TaxonomyProposal):
        self._taxonomy = taxonomy

    @classmethod
    def from_active(cls) -> "VaultRegistry | None":
        taxonomy = get_migration_store().get_active_taxonomy()
        if taxonomy is None:
            return None
        return cls(taxonomy)

    @property
    def taxonomy_id(self) -> str:
        return self._taxonomy.id

    def get_tag_hierarchy(self) -> list[str]:
        return _flatten_tags(self._taxonomy.tag_hierarchy)

    def get_link_targets(self) -> list[dict[str, str | list[str]]]:
        return [
            {"title": lt.title, "aliases": lt.aliases, "folder": lt.folder}
            for lt in self._taxonomy.link_targets
        ]

    def get_folder_structure(self) -> list[str]:
        return list(self._taxonomy.folders)
