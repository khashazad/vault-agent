from tests.factories import make_changeset


class TestChangesetStore:
    def test_set_and_get(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        retrieved = memory_changeset_store.get(cs.id)
        assert retrieved is not None
        assert retrieved.id == cs.id
        assert retrieved.status == "pending"

    def test_get_nonexistent(self, memory_changeset_store):
        assert memory_changeset_store.get("nonexistent") is None

    def test_get_all(self, memory_changeset_store):
        cs1 = make_changeset()
        cs2 = make_changeset()
        memory_changeset_store.set(cs1)
        memory_changeset_store.set(cs2)
        all_cs = memory_changeset_store.get_all()
        assert len(all_cs) == 2

    def test_upsert_updates_status(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        cs.status = "applied"
        memory_changeset_store.set(cs)
        retrieved = memory_changeset_store.get(cs.id)
        assert retrieved.status == "applied"

    def test_delete(self, memory_changeset_store):
        cs = make_changeset()
        memory_changeset_store.set(cs)
        memory_changeset_store.delete(cs.id)
        assert memory_changeset_store.get(cs.id) is None


class TestChangesetStoreFiltered:
    def test_no_filter(self, memory_changeset_store):
        cs1 = make_changeset(status="pending")
        cs2 = make_changeset(status="applied")
        memory_changeset_store.set(cs1)
        memory_changeset_store.set(cs2)
        results, total = memory_changeset_store.get_all_filtered()
        assert total == 2
        assert len(results) == 2

    def test_status_filter(self, memory_changeset_store):
        cs1 = make_changeset(status="pending")
        cs2 = make_changeset(status="applied")
        cs3 = make_changeset(status="pending")
        memory_changeset_store.set(cs1)
        memory_changeset_store.set(cs2)
        memory_changeset_store.set(cs3)
        results, total = memory_changeset_store.get_all_filtered(status="pending")
        assert total == 2
        assert len(results) == 2
        assert all(r.status == "pending" for r in results)

    def test_pagination(self, memory_changeset_store):
        for _ in range(5):
            memory_changeset_store.set(make_changeset())
        results, total = memory_changeset_store.get_all_filtered(offset=2, limit=2)
        assert total == 5
        assert len(results) == 2

    def test_empty_results(self, memory_changeset_store):
        results, total = memory_changeset_store.get_all_filtered()
        assert total == 0
        assert results == []

    def test_offset_beyond_total(self, memory_changeset_store):
        memory_changeset_store.set(make_changeset())
        results, total = memory_changeset_store.get_all_filtered(offset=100)
        assert total == 1
        assert results == []


class TestBatchJobStore:
    def test_set_and_get(self, memory_batch_job_store):
        memory_batch_job_store.set(
            paper_key="KEY1",
            batch_id="batch_123",
            status="pending",
            items_json="[]",
            created_at="2024-01-01T00:00:00Z",
        )
        job = memory_batch_job_store.get("KEY1")
        assert job is not None
        assert job["batch_id"] == "batch_123"
        assert job["status"] == "pending"

    def test_get_nonexistent(self, memory_batch_job_store):
        assert memory_batch_job_store.get("NOPE") is None

    def test_update_status(self, memory_batch_job_store):
        memory_batch_job_store.set(
            paper_key="KEY2",
            batch_id="batch_456",
            status="pending",
            items_json="[]",
            created_at="2024-01-01T00:00:00Z",
        )
        memory_batch_job_store.update_status("KEY2", "completed", "cs-id-123")
        job = memory_batch_job_store.get("KEY2")
        assert job["status"] == "completed"
        assert job["changeset_id"] == "cs-id-123"
