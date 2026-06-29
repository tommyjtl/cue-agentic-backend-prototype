from unittest.mock import MagicMock, patch

from cue_mark.telegram.client import TelegramClient


def test_send_message_falls_back_to_plain_text_on_parse_error():
    client = TelegramClient(bot_token="123:abc", base_url="https://example.test")

    with patch.object(client, "_call") as mock_call:
        mock_call.side_effect = [
            RuntimeError("Bad Request: can't parse entities: unsupported tag"),
            {"message_id": 1},
        ]
        result = client.send_message(
            "123",
            "<b>broken</b>",
            parse_mode="HTML",
            fallback_text="**broken**",
        )

    assert result == {"message_id": 1}
    assert mock_call.call_count == 2
    assert mock_call.call_args_list[1].kwargs["params"]["text"] == "**broken**"
    assert "parse_mode" not in mock_call.call_args_list[1].kwargs["params"]
