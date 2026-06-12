from cue.ocr.formatting import attachment_section, merge_hint_with_ocr_section
from cue.ocr.service import prepare_image_context


def test_attachment_section_single_image():
    section = attachment_section(1, ["Hello world"])
    assert "[Image attached — text extracted below]" in section
    assert "Hello world" in section


def test_attachment_section_multiple_images():
    section = attachment_section(2, ["First", "Second"])
    assert "[2 images attached — text extracted below]" in section
    assert "--- Image 1 ---" in section
    assert "--- Image 2 ---" in section


def test_merge_hint_with_ocr_section():
    merged = merge_hint_with_ocr_section("nice tool", "[Image attached — text extracted below]\n\nLine")
    assert merged.startswith("nice tool")
    assert "text extracted below" in merged


def test_prepare_image_context_uses_ocr_when_enabled(monkeypatch, tmp_path):
    image = tmp_path / "shot.png"
    image.write_bytes(b"fake")

    monkeypatch.setattr("cue.ocr.service.vision_ocr_available", lambda: True)
    monkeypatch.setattr(
        "cue.ocr.service.extract_text_blocks_from_paths",
        lambda paths, automatically_detect_language: ["Extracted line"],
    )

    merged, llm_paths = prepare_image_context(
        "check this",
        [image],
        ocr_enabled=True,
        automatically_detect_language=False,
    )
    assert llm_paths == []
    assert "check this" in merged
    assert "Extracted line" in merged


def test_prepare_image_context_falls_back_to_raw_images_when_disabled(tmp_path):
    image = tmp_path / "shot.png"
    image.write_bytes(b"fake")

    hint, llm_paths = prepare_image_context(
        "check this",
        [image],
        ocr_enabled=False,
        automatically_detect_language=False,
    )
    assert hint == "check this"
    assert llm_paths == [image]
