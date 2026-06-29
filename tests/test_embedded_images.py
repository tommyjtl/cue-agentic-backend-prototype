from datetime import datetime, timezone
from pathlib import Path

from cue.obsidian.images import (
    LINQ_ASSETS_DIR,
    append_linq_asset_images,
    markdown_link_for_asset,
    save_linq_assets,
)


def test_save_linq_assets(tmp_path: Path):
    vault = tmp_path / "vault"
    source = tmp_path / "shot.png"
    source.write_bytes(b"image-bytes")
    captured_at = datetime(2026, 6, 12, 15, 30, tzinfo=timezone.utc)

    saved = save_linq_assets(vault, [source], captured_at)

    assert len(saved) == 1
    assert saved[0].parent == vault / LINQ_ASSETS_DIR
    assert saved[0].name == "20260612-153000-1.png"
    assert saved[0].read_bytes() == b"image-bytes"


def test_markdown_link_for_asset():
    asset = Path("/vault/linq-assets/20260612-153000-1.png")
    assert markdown_link_for_asset(asset, label="Image 1") == "![Image 1](../linq-assets/20260612-153000-1.png)"


def test_append_linq_asset_images(tmp_path: Path):
    vault = tmp_path / "vault"
    source = tmp_path / "shot.jpg"
    source.write_bytes(b"abc")
    captured_at = datetime(2026, 6, 12, 15, 30, tzinfo=timezone.utc)

    body = append_linq_asset_images(
        "## Highlights\n\n- One",
        vault_root=vault,
        image_paths=[source],
        captured_at=captured_at,
    )

    assert "## Highlights" in body
    assert "## Attachments" in body
    assert "![Image](../linq-assets/20260612-153000-1.jpg)" in body
    assert (vault / LINQ_ASSETS_DIR / "20260612-153000-1.jpg").exists()
    assert "base64" not in body
