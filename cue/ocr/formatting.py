from __future__ import annotations


def normalized_block(text: str) -> str:
    trimmed = text.strip()
    return trimmed if trimmed else "(No text recognized in image.)"


def attachment_section(image_count: int, extracted_blocks: list[str]) -> str:
    header = (
        "[Image attached — text extracted below]"
        if image_count == 1
        else f"[{image_count} images attached — text extracted below]"
    )

    if image_count <= 1:
        return f"{header}\n\n{normalized_block(extracted_blocks[0] if extracted_blocks else '')}"

    sections = [header]
    for index, block in enumerate(extracted_blocks, start=1):
        sections.append(f"--- Image {index} ---\n{normalized_block(block)}")
    return "\n\n".join(sections)


def merge_hint_with_ocr_section(user_hint: str, ocr_section: str) -> str:
    hint = user_hint.strip()
    if not hint:
        return ocr_section
    return f"{hint}\n\n{ocr_section}"
