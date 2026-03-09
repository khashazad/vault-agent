import asyncio
import logging
from dataclasses import asdict

from src.config import AppConfig

logger = logging.getLogger("vault-agent")

SYNC_INTERVAL_SECONDS = 5 * 60  # 5 minutes


class ZoteroPaperCacheSyncer:
    def __init__(self, config: AppConfig):
        self._config = config
        self._task: asyncio.Task | None = None
        self._sync_in_progress = False
        self._trigger_event = asyncio.Event()

    @property
    def sync_in_progress(self) -> bool:
        return self._sync_in_progress

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("Zotero paper cache sync started")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("Zotero paper cache sync stopped")

    def trigger_sync(self) -> None:
        """Trigger an immediate sync cycle."""
        self._trigger_event.set()

    async def _sync_loop(self) -> None:
        # Run first sync immediately
        await self._do_sync()

        while True:
            try:
                # Wait for either the interval or a manual trigger
                try:
                    await asyncio.wait_for(
                        self._trigger_event.wait(),
                        timeout=SYNC_INTERVAL_SECONDS,
                    )
                    self._trigger_event.clear()
                except asyncio.TimeoutError:
                    pass  # Normal interval elapsed

                await self._do_sync()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in Zotero paper cache sync loop")
                # Wait a bit before retrying after an unexpected error
                await asyncio.sleep(30)

    async def _do_sync(self) -> None:
        self._sync_in_progress = True
        try:
            from src.zotero.client import ZoteroClient
            from src.zotero.sync import ZoteroSyncState

            client = ZoteroClient(
                library_id=self._config.zotero_library_id,
                library_type=self._config.zotero_library_type,
                api_key=self._config.zotero_api_key,
            )
            sync_state = ZoteroSyncState()

            try:
                papers = await asyncio.to_thread(client.fetch_papers, None)
                paper_dicts = [asdict(p) for p in papers]
                await asyncio.to_thread(sync_state.upsert_papers, paper_dicts)

                current_keys = {p.key for p in papers}
                deleted = await asyncio.to_thread(
                    sync_state.delete_papers_not_in, current_keys
                )

                logger.info(
                    "Zotero paper cache synced: %d papers cached, %d removed",
                    len(papers),
                    deleted,
                )
            except Exception:
                logger.exception("Failed to sync Zotero paper cache")

            try:
                collections = await asyncio.to_thread(client.fetch_collections)
                collection_dicts = [asdict(c) for c in collections]
                await asyncio.to_thread(sync_state.upsert_collections, collection_dicts)
                current_collection_keys = {c.key for c in collections}
                deleted_cols = await asyncio.to_thread(
                    sync_state.delete_collections_not_in, current_collection_keys
                )
                logger.info(
                    "Zotero collection cache synced: %d collections cached, %d removed",
                    len(collections),
                    deleted_cols,
                )
            except Exception:
                logger.exception("Failed to sync Zotero collection cache")
        except Exception:
            logger.exception("Failed to initialize Zotero sync")
        finally:
            self._sync_in_progress = False
