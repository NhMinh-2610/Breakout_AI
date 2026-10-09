import pytest
from concurrent.futures import ThreadPoolExecutor

from breakout_ai.storage import QuotaExceeded, Store


def save(store, conversation=None, limit=40):
    return store.save_turn("P/E là gì", "Ví dụ [K02]", {"sources": []}, "BOTH", conversation, limit)


def test_messages_and_watchlist_persist(settings, store):
    conversation = save(store)
    store.upsert_watch("VN", "fpt", "Đọc báo cáo")
    reloaded = Store(settings.database_path)
    assert [m["role"] for m in reloaded.messages(conversation)] == ["user", "assistant"]
    assert reloaded.watchlist()[0]["symbol"] == "FPT"


def test_workspace_isolation_covers_reads_updates_and_deletes(settings, store):
    conversation = save(store)
    store.upsert_watch("US", "AAPL", "Nghiên cứu")
    watch = store.watchlist()[0]
    other = Store(settings.database_path, "other")
    assert other.messages(conversation) == []
    assert other.conversations() == other.watchlist() == []
    other.delete_conversation(conversation)
    other.remove_watch(watch["id"])
    with pytest.raises(ValueError):
        save(other, conversation)
    assert len(store.messages(conversation)) == 2
    assert len(store.watchlist()) == 1


def test_quota_rejection_does_not_create_partial_conversation(store):
    save(store, limit=1)
    with pytest.raises(QuotaExceeded):
        save(store, limit=1)
    assert len(store.conversations()) == 1 and store.usage() == 1


def test_deleting_a_conversation_cascades_messages(store):
    conversation = save(store)
    store.delete_conversation(conversation)
    assert store.messages(conversation) == []
    assert store.usage() == 1  # Deleting chat must not reset the rolling quota.


def test_watchlist_identity_includes_market_and_upsert_preserves_one_record(store):
    store.upsert_watch("VN", "DEMO", "old")
    store.upsert_watch("VN", "DEMO", "new")
    store.upsert_watch("US", "DEMO", "US note")
    assert len(store.watchlist()) == 2
    assert next(r for r in store.watchlist() if r["market"] == "VN")["note"] == "new"


def test_simultaneous_writes_cannot_exceed_quota(store):
    def attempt(_):
        try:
            save(store, limit=1)
            return "saved"
        except QuotaExceeded:
            return "limited"
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(attempt, range(2))) == ["limited", "saved"]
    assert store.usage() == 1 and len(store.conversations()) == 1


@pytest.mark.parametrize("legacy_version", [1, 2, 3])
def test_additive_schema_upgrade_retains_legacy_conversations(settings, store, legacy_version):
    identifier = save(store)
    with store.connection() as db:
        db.execute(f"PRAGMA user_version = {legacy_version}")
    reloaded = Store(settings.database_path)
    assert len(reloaded.messages(identifier)) == 2 and reloaded.usage() == 1


def test_unknown_future_schema_is_not_overwritten(settings, store):
    with store.connection() as db:
        db.execute("PRAGMA user_version = 99")
    with pytest.raises(ValueError, match="schema"):
        Store(settings.database_path)


def test_conversation_rename_is_persistent_and_workspace_scoped(settings, store):
    identifier = save(store)
    other = Store(settings.database_path, "other")
    other.rename_conversation(identifier, "Foreign title")
    assert store.conversations()[0]["title"] != "Foreign title"
    store.rename_conversation(identifier, "Research notes")
    assert Store(settings.database_path).conversations()[0]["title"] == "Research notes"
    with pytest.raises(ValueError):
        store.rename_conversation(identifier, "   ")
