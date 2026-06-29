from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cue_mark.models import CaptureRequest
from cue_mark.service import MarkService


@pytest.fixture
def mark_service(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr("cue_mark.service.settings.mark_vault_root", str(vault))
    monkeypatch.setattr("cue_mark.service.settings.mark_embed_images", True)
    monkeypatch.setattr("cue_mark.service.settings.ocr_enabled", True)
    monkeypatch.setattr("cue_mark.service.settings.ocr_auto_detect_language", False)

    service = MarkService(search_service=MagicMock())
    return service


def test_standalone_capture_saves_telegram_assets_without_sending_to_llm(
    monkeypatch,
    mark_service: MarkService,
    tmp_path: Path,
):
    image = tmp_path / "shot.png"
    image.write_bytes(b"fake-image-bytes")

    llm_image_paths_seen: list[list[Path]] = []

    monkeypatch.setattr(
        "cue_mark.service.prepare_image_context",
        lambda user_hint, image_paths, ocr_enabled, automatically_detect_language: (
            f"{user_hint}\n\n[Image attached — text extracted below]\n\nOCR text",
            [],
        ),
    )
    monkeypatch.setattr(
        "cue_mark.service.parse_generated_note",
        lambda response_text, fallback_title: MagicMock(title="Capture", body="## Highlights\n\n- Saved."),
    )

    def fake_chat_text(*args, image_paths=None, **kwargs):
        llm_image_paths_seen.append(list(image_paths or []))
        return '{"title":"Capture","body":"## Highlights\\n\\n- Saved."}'

    monkeypatch.setattr("cue_mark.service.chat_text", fake_chat_text)

    result = mark_service.capture(
        CaptureRequest(
            text="check this screenshot",
            image_paths=[str(image)],
            sync_index=False,
        )
    )

    assert llm_image_paths_seen == [[]]
    written = Path(result.file_path).read_text(encoding="utf-8")
    assert "## Attachments" in written
    assert "../telegram-assets/" in written
    assert "base64" not in written
    assets = list((tmp_path / "vault" / "telegram-assets").glob("*.png"))
    assert len(assets) == 1
    assert assets[0].read_bytes() == b"fake-image-bytes"
