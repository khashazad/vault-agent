import pytest
from httpx import AsyncClient, ASGITransport

from src.server import app
from tests.factories import make_changeset
import src.store as store_module
from src.store import ChangesetStore


@pytest.fixture
async def client(tmp_vault, app_config, tmp_path):
    """httpx AsyncClient with app.state.config set for testing."""
    app.state.config = app_config

    # Inject in-memory stores
    mem_cs = ChangesetStore(db_path=":memory:")
    old_cs = store_module._changeset_store
    store_module._changeset_store = mem_cs

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    store_module._changeset_store = old_cs
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
        from src.store import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.get(f"/changesets/{cs.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cs.id

    async def test_reject_changeset(self, client):
        from src.store import get_changeset_store

        cs = make_changeset()
        get_changeset_store().set(cs)

        resp = await client.post(f"/changesets/{cs.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_update_change_status(self, client):
        from src.store import get_changeset_store

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
        from src.store import get_changeset_store
        from tests.factories import make_proposed_change

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
