import pytest
from httpx import AsyncClient, ASGITransport

import src.db as db_module
from src.db import ChangesetStore, SettingsStore
from src.server import app


@pytest.fixture
def memory_settings_store():
    s = SettingsStore(db_path=":memory:")
    old = db_module._settings_store
    db_module._settings_store = s
    yield s
    db_module._settings_store = old
    s.close()


@pytest.fixture
def memory_changeset_store():
    s = ChangesetStore(db_path=":memory:")
    old = db_module._changeset_store
    db_module._changeset_store = s
    yield s
    db_module._changeset_store = old
    s.close()


@pytest.fixture
async def client(tmp_vault, app_config, memory_settings_store, memory_changeset_store):
    app.state.config = app_config
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestClawdyConfig:
    async def test_get_config_defaults(self, client):
        res = await client.get("/clawdy/config")
        assert res.status_code == 200
        data = res.json()
        assert data["copy_vault_path"] is None
        assert data["interval"] == 300
        assert data["enabled"] is False

    async def test_put_config(self, client, tmp_path, memory_settings_store):
        copy_vault = tmp_path / "copy"
        copy_vault.mkdir()
        (copy_vault / ".git").mkdir()

        res = await client.put("/clawdy/config", json={
            "copy_vault_path": str(copy_vault),
            "interval": 60,
            "enabled": True,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["copy_vault_path"] == str(copy_vault)
        assert data["interval"] == 60
        assert data["enabled"] is True

    async def test_put_config_invalid_path(self, client):
        res = await client.put("/clawdy/config", json={
            "copy_vault_path": "/nonexistent/path",
        })
        assert res.status_code == 400


@pytest.mark.asyncio
class TestClawdyStatus:
    async def test_get_status(self, client):
        res = await client.get("/clawdy/status")
        assert res.status_code == 200
        data = res.json()
        assert "enabled" in data
        assert "last_poll" in data
        assert "pending_changeset_count" in data


@pytest.mark.asyncio
class TestChangesetSourceTypeFilter:
    async def test_filter_by_source_type(self, client, memory_changeset_store):
        from tests.factories import make_changeset
        cs_web = make_changeset(source_type="web")
        cs_clawdy = make_changeset(source_type="clawdy", items=[], routing=None)
        memory_changeset_store.set(cs_web)
        memory_changeset_store.set(cs_clawdy)

        res = await client.get("/changesets?source_type=clawdy")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["changesets"][0]["source_type"] == "clawdy"


@pytest.mark.asyncio
class TestClawdyBidirectional:
    async def test_converge_sets_last_converge_timestamp(self, client, memory_changeset_store, memory_settings_store, tmp_vault, tmp_path):
        from tests.factories import make_changeset, make_proposed_change
        from unittest.mock import patch

        copy_vault = tmp_path / "copy"
        copy_vault.mkdir()
        (copy_vault / ".git").mkdir()
        memory_settings_store.set("clawdy_copy_vault_path", str(copy_vault))

        # Create a fully-resolved clawdy changeset with a rejected change
        change = make_proposed_change(
            tool_name="replace_note",
            input={"path": "Notes/A.md", "content": "new"},
            status="rejected",
        )
        cs = make_changeset(source_type="clawdy", items=[], routing=None, changes=[change])
        memory_changeset_store.set(cs)

        # Write file in both vaults so converge_vaults can read main and write copy
        for vault in [tmp_vault, copy_vault]:
            notes = vault / "Notes"
            notes.mkdir(parents=True, exist_ok=True)
            (notes / "A.md").write_text("old content")

        # Mock clawdy_service and git operations
        from unittest.mock import MagicMock
        import src.server as server_mod
        mock_svc = MagicMock()
        mock_svc.copy_vault_path = str(copy_vault)
        old_global = server_mod.clawdy_service
        server_mod.clawdy_service = mock_svc

        try:
            with patch("src.server.git_commit"), patch("src.server.git_push"), patch("src.server.git_status", return_value="M Notes/A.md\n"):
                res = await client.post(f"/clawdy/converge/{cs.id}")
        finally:
            server_mod.clawdy_service = old_global

        assert res.status_code == 200
        assert memory_settings_store.get("clawdy_last_converge") is not None

    async def test_status_includes_bidirectional_fields(self, client):
        res = await client.get("/clawdy/status")
        assert res.status_code == 200
        data = res.json()
        assert "last_auto_sync" in data
        assert "bidirectional_enabled" in data
        assert data["bidirectional_enabled"] is False

    async def test_config_change_resets_last_converge(self, client, memory_settings_store, tmp_path):
        memory_settings_store.set("clawdy_last_converge", "2026-01-01T00:00:00+00:00")

        new_copy = tmp_path / "new_copy"
        new_copy.mkdir()
        (new_copy / ".git").mkdir()

        await client.put("/clawdy/config", json={"copy_vault_path": str(new_copy)})
        assert memory_settings_store.get("clawdy_last_converge") is None
