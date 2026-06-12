from __future__ import annotations

from cue.ocr.formatting import attachment_section, merge_hint_with_ocr_section


def extract_text_blocks_from_paths(
    image_paths: list,
    *,
    automatically_detect_language: bool,
) -> list[str]:
    from cue.ocr.vision import extract_structured_text

    return [
        extract_structured_text(path, automatically_detect_language=automatically_detect_language)
        for path in image_paths
    ]


def prepare_image_context(
    user_hint: str,
    image_paths: list,
    *,
    ocr_enabled: bool,
    automatically_detect_language: bool,
) -> tuple[str, list]:
    if not image_paths:
        return user_hint, []

    if not ocr_enabled or not vision_ocr_available():
        return user_hint, image_paths

    blocks = extract_text_blocks_from_paths(
        image_paths,
        automatically_detect_language=automatically_detect_language,
    )
    ocr_section = attachment_section(len(image_paths), blocks)
    return merge_hint_with_ocr_section(user_hint, ocr_section), []


def vision_ocr_available() -> bool:
    try:
        import Vision  # noqa: F401
        import Quartz  # noqa: F401

        return True
    except ImportError:
        return False
