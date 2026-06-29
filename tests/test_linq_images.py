from pathlib import Path
from unittest.mock import MagicMock

from cue_mark.linq.handler import LinqWebhookHandler
from cue_mark.linq.parser import InboundMessage


def test_download_images_deduplicates_same_attachment_url():
    client = MagicMock()
    client.get_attachment.return_value = {
        "download_url": "https://cdn.example.com/image.png",
        "content_type": "image/png",
        "filename": "image.png",
    }
    client.download_url.return_value = b"same-image"

    inbound = InboundMessage(
        event_id="evt-1",
        chat_id="chat-1",
        sender_handle="+1",
        text="",
        media_urls=["https://cdn.example.com/image.png"],
        attachment_ids=["att-123"],
    )

    handler = LinqWebhookHandler()
    downloaded = handler._download_images(client, inbound)

    assert len(downloaded) == 1
    assert client.download_url.call_count == 1
    assert downloaded[0].read_bytes() == b"same-image"

    for path in downloaded:
        path.unlink(missing_ok=True)
    downloaded[0].parent.rmdir()
