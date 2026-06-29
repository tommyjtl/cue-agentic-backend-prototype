from pathlib import Path
from unittest.mock import MagicMock

from cue_mark.telegram.handler import TelegramUpdateHandler
from cue_mark.telegram.parser import InboundMessage
from cue_mark.telegram.store import TelegramEventStore


def test_download_images_fetches_each_file_id(tmp_path: Path):
    client = MagicMock()
    client.get_file.return_value = {"file_path": "photos/file.jpg"}
    client.download_file.return_value = b"image-bytes"

    inbound = InboundMessage(
        event_id="10001",
        chat_id="123",
        sender_id="123456789",
        text="",
        photo_file_ids=["file-abc"],
    )

    handler = TelegramUpdateHandler(event_store=TelegramEventStore(tmp_path / "jobs.sqlite3"))
    downloaded = handler._download_images(client, inbound)

    assert len(downloaded) == 1
    client.get_file.assert_called_once_with("file-abc")
    client.download_file.assert_called_once_with("photos/file.jpg")
    assert downloaded[0].read_bytes() == b"image-bytes"

    for path in downloaded:
        path.unlink(missing_ok=True)
    downloaded[0].parent.rmdir()
