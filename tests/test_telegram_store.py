from cue_mark.telegram.store import TelegramEventStore


def test_poll_offset_round_trip(tmp_path):
    store = TelegramEventStore(tmp_path / "jobs.sqlite3")
    assert store.get_poll_offset() is None
    store.set_poll_offset(42)
    assert store.get_poll_offset() == 42
