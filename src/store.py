from datetime import datetime, timezone, timedelta

from src.models import Changeset

MAX_AGE = timedelta(hours=1)


class ChangesetStore:
    def __init__(self):
        self._store: dict[str, Changeset] = {}

    def set(self, changeset: Changeset) -> None:
        self._store[changeset.id] = changeset

    def get(self, changeset_id: str) -> Changeset | None:
        return self._store.get(changeset_id)

    def get_all(self) -> list[Changeset]:
        return list(self._store.values())

    def delete(self, changeset_id: str) -> None:
        self._store.pop(changeset_id, None)

    def cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            cid
            for cid, cs in self._store.items()
            if (now - datetime.fromisoformat(cs.created_at)) > MAX_AGE
        ]
        for cid in expired:
            del self._store[cid]


changeset_store = ChangesetStore()
