from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

TELEGRAM_ASSETS_DIR = "telegram-assets"


def save_telegram_assets(
    vault_root: Path,
    image_paths: list[Path],
    captured_at: datetime,
) -> list[Path]:
    assets_dir = vault_root / TELEGRAM_ASSETS_DIR
    assets_dir.mkdir(parents=True, exist_ok=True)

    stamp = captured_at.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    saved: list[Path] = []

    for index, source in enumerate(image_paths, start=1):
        suffix = source.suffix.lower() or ".jpg"
        target = assets_dir / f"{stamp}-{index}{suffix}"
        collision_index = 2
        while target.exists():
            target = assets_dir / f"{stamp}-{index}-{collision_index}{suffix}"
            collision_index += 1

        shutil.copy2(source, target)
        saved.append(target)

    return saved


def markdown_link_for_asset(asset_path: Path, *, label: str) -> str:
    relative_path = Path("..") / TELEGRAM_ASSETS_DIR / asset_path.name
    return f"![{label}]({relative_path.as_posix()})"


def append_telegram_asset_images(
    body: str,
    *,
    vault_root: Path,
    image_paths: list[Path],
    captured_at: datetime,
) -> str:
    if not image_paths:
        return body

    saved_assets = save_telegram_assets(vault_root, image_paths, captured_at)
    lines = [body.rstrip(), "", "## Attachments", ""]
    for index, asset_path in enumerate(saved_assets, start=1):
        label = "Image" if len(saved_assets) == 1 else f"Image {index}"
        lines.append(markdown_link_for_asset(asset_path, label=label))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
