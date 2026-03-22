from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from src.server import app
from tests.factories import make_changeset, make_proposed_change
import src.db as db_module
from src.db import ChangesetStore


@pytest.fixture
async def client(tmp_vault, app_config, tmp_path):
    """httpx AsyncClient with app.state.config set for testing."""
    app.state.config = app_config

    # Inject in-memory stores
    mem_cs = ChangesetStore(db_path=":memory:")
    old_cs = db_module._changeset_store
    db_module._changeset_store = mem_cs

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    db_module._changeset_store = old_cs
    mem_cs.close()


class TestHealthRoute:
    async def test_health_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["vaultConfigured"] is True


class TestVaultMapRoute:
    async def test_vault_map(self, client):
        resp = await client.get("/vault/map")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalNotes"] == 4


class TestChangesetRoutes:
    async def test_get_nonexistent_changeset(self, client):
        resp = await client.get("/changesets/nonexistent")
        assert resp.status_code == 404

    async def test_changeset_crud(self, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.get(f"/changesets/{cs.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cs.id

    async def test_reject_changeset(self, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.post(f"/changesets/{cs.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_update_change_status(self, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        change_id = cs.changes[0].id
        get_changeset_store().set(cs)

        resp = await client.patch(
            f"/changesets/{cs.id}/changes/{change_id}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_apply_changeset(self, client, tmp_vault):
        from src.db import get_changeset_store

        change = make_proposed_change(
            tool_name="create_note",
            input={"path": "Applied/Test.md", "content": "# Test"},
            status="approved",
        )
        cs = make_changeset(changes=[change])
        get_changeset_store().set(cs)

        resp = await client.post(f"/changesets/{cs.id}/apply")
        assert resp.status_code == 200
        data = resp.json()
        assert change.id in data["applied"]


class TestChangesetHistoryRoutes:
    async def test_list_changesets_empty(self, client):
        resp = await client.get("/changesets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["changesets"] == []
        assert data["total"] == 0

    async def test_list_changesets_with_data(self, client):
        from src.db import get_changeset_store

        store = get_changeset_store()
        store.set(make_changeset(status="pending"))
        store.set(make_changeset(status="applied"))

        resp = await client.get("/changesets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["changesets"]) == 2
        # Should have change_count field
        assert "change_count" in data["changesets"][0]

    async def test_list_changesets_filtered(self, client):
        from src.db import get_changeset_store

        store = get_changeset_store()
        store.set(make_changeset(status="pending"))
        store.set(make_changeset(status="applied"))

        resp = await client.get("/changesets?status=applied")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["changesets"][0]["status"] == "applied"

    async def test_list_changesets_paginated(self, client):
        from src.db import get_changeset_store

        store = get_changeset_store()
        for _ in range(3):
            store.set(make_changeset())

        resp = await client.get("/changesets?offset=1&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["changesets"]) == 1

    async def test_update_change_content(self, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        change_id = cs.changes[0].id
        get_changeset_store().set(cs)

        resp = await client.patch(
            f"/changesets/{cs.id}/changes/{change_id}",
            json={"proposed_content": "# Updated\n\nNew content."},
        )
        assert resp.status_code == 200

        # Verify content was updated
        updated = get_changeset_store().get(cs.id)
        assert updated.changes[0].proposed_content == "# Updated\n\nNew content."
        assert "Updated" in updated.changes[0].diff

    async def test_request_changes(self, client):
        from src.db import get_changeset_store

        cs = make_changeset(status="pending")
        get_changeset_store().set(cs)

        resp = await client.post(
            f"/changesets/{cs.id}/request-changes",
            json={"feedback": "Use a different heading"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "revision_requested"
        assert data["feedback"] == "Use a different heading"

    async def test_request_changes_wrong_status(self, client):
        from src.db import get_changeset_store

        cs = make_changeset(status="applied")
        get_changeset_store().set(cs)

        resp = await client.post(
            f"/changesets/{cs.id}/request-changes",
            json={"feedback": "test"},
        )
        assert resp.status_code == 400

    async def test_request_changes_404(self, client):
        resp = await client.post(
            "/changesets/nonexistent/request-changes",
            json={"feedback": "test"},
        )
        assert resp.status_code == 404

    async def test_regenerate_wrong_status(self, client):
        from src.db import get_changeset_store

        cs = make_changeset(status="pending")
        get_changeset_store().set(cs)

        resp = await client.post(f"/changesets/{cs.id}/regenerate")
        assert resp.status_code == 400

    @patch("src.server.generate_zotero_note", new_callable=AsyncMock)
    async def test_regenerate_success(self, mock_gen, client):
        from src.db import get_changeset_store

        cs = make_changeset(
            status="revision_requested",
            feedback="Fix heading",
            source_type="zotero",
        )
        get_changeset_store().set(cs)

        new_cs = make_changeset(parent_changeset_id=cs.id)
        mock_gen.return_value = new_cs

        resp = await client.post(f"/changesets/{cs.id}/regenerate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_changeset_id"] == cs.id

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs["feedback"] == "Fix heading"
        assert call_kwargs.kwargs["parent_changeset_id"] == cs.id

    async def test_delete_changeset(self, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.delete(f"/changesets/{cs.id}")
        assert resp.status_code == 204
        assert get_changeset_store().get(cs.id) is None

    async def test_delete_changeset_not_found(self, client):
        resp = await client.delete("/changesets/nonexistent")
        assert resp.status_code == 404

    @patch("src.zotero.sync.ZoteroSyncState")
    async def test_delete_changeset_clears_paper_sync(self, mock_cls, client):
        from src.db import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.delete(f"/changesets/{cs.id}")
        assert resp.status_code == 204

        mock_cls.return_value.clear_paper_sync_by_changeset.assert_called_once_with(
            cs.id
        )


class TestVaultAssetRoute:
    async def test_serve_existing_file(self, client, tmp_vault):
        resp = await client.get("/vault/assets/Projects/My Project.md")
        assert resp.status_code == 200
        assert b"# My Project" in resp.content

    async def test_serve_image_file(self, client, tmp_vault):
        # Create a fake image
        img_dir = tmp_vault / "attachments"
        img_dir.mkdir()
        (img_dir / "test.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        resp = await client.get("/vault/assets/attachments/test.png")
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    async def test_nonexistent_file_404(self, client, tmp_vault):
        resp = await client.get("/vault/assets/does-not-exist.md")
        assert resp.status_code == 404

    async def test_filename_fallback_resolution(self, client, tmp_vault):
        # Image in a subfolder, requested by basename only
        img_dir = tmp_vault / "attachments"
        img_dir.mkdir(exist_ok=True)
        (img_dir / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        resp = await client.get("/vault/assets/diagram.png")
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    async def test_fallback_skips_hidden_dirs(self, client, tmp_vault):
        hidden = tmp_vault / ".obsidian" / "plugins"
        hidden.mkdir(parents=True, exist_ok=True)
        (hidden / "secret.json").write_text("{}")

        resp = await client.get("/vault/assets/secret.json")
        assert resp.status_code == 404

    @patch("src.vault.validate_path", side_effect=ValueError("escapes vault"))
    async def test_path_traversal_rejected(self, mock_vp, client, tmp_vault):
        resp = await client.get("/vault/assets/sneaky/path")
        assert resp.status_code == 400


class TestMigrationRoutes:
    @patch("src.migration.migrator.run_migration", new_callable=AsyncMock)
    @patch("src.migration.migrator.create_migration_job")
    async def test_create_job_expands_tilde(self, mock_create, mock_run, client):
        from src.models.migration import MigrationJob

        mock_create.return_value = MigrationJob(
            id="test-id",
            source_vault="/src",
            target_vault="/expanded",
            status="pending",
            total_notes=0,
            created_at="2026-03-20T00:00:00",
        )

        resp = await client.post(
            "/migration/jobs",
            json={"target_vault": "~/Documents/test-vault", "batch": False},
        )
        assert resp.status_code == 200

        called_target = mock_create.call_args[0][1]
        assert "~" not in called_target
        assert called_target.startswith("/")


class TestVaultTaxonomyRoutes:
    async def test_get_taxonomy(self, client):
        resp = await client.get("/vault/taxonomy")
        assert resp.status_code == 200
        data = resp.json()
        assert "folders" in data
        assert "tags" in data
        assert "tag_hierarchy" in data
        assert "link_targets" in data
        assert data["total_notes"] == 4

    async def test_get_taxonomy_has_tags(self, client):
        resp = await client.get("/vault/taxonomy")
        data = resp.json()
        tag_names = {t["name"] for t in data["tags"]}
        assert "project" in tag_names
        assert "ml" in tag_names

    async def test_apply_rename_tag(self, client):
        resp = await client.post(
            "/vault/taxonomy/apply",
            json={"operations": [{"op": "rename_tag", "target": "ml", "value": "machine-learning"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "changeset_id" in data
        assert data["change_count"] >= 1

        # Verify changeset was created
        cs_resp = await client.get(f"/changesets/{data['changeset_id']}")
        assert cs_resp.status_code == 200

    async def test_apply_rename_link(self, client):
        resp = await client.post(
            "/vault/taxonomy/apply",
            json={"operations": [{"op": "rename_link", "target": "Machine Learning", "value": "ML Overview"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["change_count"] >= 1

    async def test_apply_no_ops_returns_400(self, client):
        resp = await client.post(
            "/vault/taxonomy/apply",
            json={"operations": []},
        )
        assert resp.status_code == 400
