from cue_mark.telegram.parser import parse_update

TEXT_UPDATE = {
    "update_id": 10001,
    "message": {
        "message_id": 42,
        "from": {"id": 123456789, "is_bot": False, "first_name": "Tommy"},
        "chat": {"id": 123456789, "type": "private"},
        "date": 1718000000,
        "text": "Saving this MLX post https://example.com/mlx",
        "entities": [
            {"offset": 21, "length": 23, "type": "url"},
        ],
    },
}


def test_parse_text_update():
    inbound = parse_update(TEXT_UPDATE)
    assert inbound is not None
    assert inbound.event_id == "10001"
    assert inbound.chat_id == "123456789"
    assert inbound.sender_id == "123456789"
    assert inbound.text == "Saving this MLX post https://example.com/mlx"
    assert inbound.urls == ["https://example.com/mlx"]


def test_parse_photo_update():
    update = {
        "update_id": 10002,
        "message": {
            "message_id": 43,
            "from": {"id": 123456789, "is_bot": False},
            "chat": {"id": 123456789, "type": "private"},
            "date": 1718000001,
            "caption": "screenshot",
            "photo": [
                {"file_id": "small", "width": 90, "height": 90},
                {"file_id": "large-file-id", "width": 800, "height": 600},
            ],
        },
    }

    inbound = parse_update(update)
    assert inbound is not None
    assert inbound.text == "screenshot"
    assert inbound.photo_file_ids == ["large-file-id"]


def test_parse_ignores_non_message_update():
    assert parse_update({"update_id": 10003}) is None
