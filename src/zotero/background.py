import asyncio
import logging
from dataclasses import asdict

from pyzotero.zotero_errors import PyZoteroError

from src.config import AppConfig

logger = logging.getLogger("vault-agent")


# Background syncer that periodically refreshes the local Zotero paper and collection cache.
class ZoteroPaperCacheSyncer:
    # Initialize the syncer with app config.
    #
    # Args:
    #     config: App config with Zotero credentials.
    def __init__(self, config: AppConfig):
        self._config = config
        self._task: asyncio.Task | None = None
        self._sync_in_progress = False
        self._trigger_event = asyncio.Event()

    # Whether a sync cycle is currently running.
    @property
    def sync_in_progress(self) -> bool:
        return self._sync_in_progress

    # Start the background sync loop as an asyncio task.
    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("Zotero paper cache sync started")

    # Cancel the background sync task.
    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("Zotero paper cache sync stopped")

    # Trigger an immediate sync cycle by signaling the event loop.
    def trigger_sync(self) -> None:
        self._trigger_event.set()

    # Event loop that runs sync on startup, then waits for trigger signals.
    async def _sync_loop(self) -> None:
        # Run first sync immediately
        await self._do_sync()

        while True:
            try:
                await self._trigger_event.wait()
                self._trigger_event.clear()

                await self._do_sync()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in Zotero paper cache sync loop")
                # Wait a bit before retrying after an unexpected error
                await asyncio.sleep(30)

    # Execute a full sync: fetch papers, collections, and annotation counts from Zotero API.
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

            await self._sync_papers(client, sync_state)
            await self._sync_collections(client, sync_state)
        except (PyZoteroError, ConnectionError, TimeoutError) as err:
            logger.error("Zotero API error during sync: %s", err)
        except Exception:
            logger.exception("Unexpected error during Zotero sync")
        finally:
            self._sync_in_progress = False

    async def _sync_papers(self, client, sync_state) -> None:
        papers = await asyncio.to_thread(client.fetch_papers, None)
        paper_dicts = [asdict(p) for p in papers]
        await asyncio.to_thread(sync_state.upsert_papers, paper_dicts)

        current_keys = {p.key for p in papers}
        deleted = await asyncio.to_thread(sync_state.delete_papers_not_in, current_keys)

        logger.info(
            "Zotero paper cache synced: %d papers cached, %d removed",
            len(papers),
            deleted,
        )

        # Fetch annotation counts per paper
        try:
            counts = await asyncio.to_thread(client.count_annotations_per_paper)
            if counts:
                await asyncio.to_thread(sync_state.update_annotation_counts, counts)
                logger.info(
                    "Annotation counts updated for %d papers",
                    len(counts),
                )
        except (PyZoteroError, ConnectionError, TimeoutError) as err:
            logger.warning("Failed to fetch annotation counts: %s", err)

    async def _sync_collections(self, client, sync_state) -> None:
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
