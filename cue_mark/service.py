from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cue.config import settings
from cue.llm.chat import chat_text
from cue.obsidian.images import append_linq_asset_images
from cue.obsidian.writer import (
    ExportKind,
    Reference,
    WriteInput,
    write_note,
)
from cue_mark.enrich import extract_urls, fetch_page_context, primary_page_context_message
from cue_mark.models import CaptureRequest, MarkResponse
from cue_mark.parser import JSON_RETRY_USER_MESSAGE, MarkParseError, parse_generated_note
from cue_mark.prompts import build_page_system_prompt, build_standalone_system_prompt
from cue_search.models import LLMConfig
from cue_search.search_service import SearchService
from cue.ocr.service import prepare_image_context


class MarkService:
    def __init__(self, search_service: SearchService | None = None) -> None:
        self.search_service = search_service or SearchService()

    def capture(self, request: CaptureRequest) -> MarkResponse:
        vault_root = settings.mark_vault_dir
        image_paths = [Path(path).expanduser().resolve() for path in request.image_paths]
        for path in image_paths:
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {path}")

        urls = extract_urls(request.text, request.urls)
        user_hint = request.text.strip()
        llm_config = LLMConfig(
            provider=settings.mark_llm_provider,
            base_url=settings.mark_llm_base_url,
            model=settings.mark_llm_model,
            api_key=settings.mark_llm_api_key,
        )

        if urls:
            return self._capture_page(
                request=request,
                vault_root=vault_root,
                user_hint=user_hint,
                url=urls[0],
                image_paths=image_paths,
                llm_config=llm_config,
            )

        return self._capture_standalone(
            request=request,
            vault_root=vault_root,
            user_hint=user_hint,
            image_paths=image_paths,
            llm_config=llm_config,
        )

    def _capture_page(
        self,
        *,
        request: CaptureRequest,
        vault_root: Path,
        user_hint: str,
        url: str,
        image_paths: list[Path],
        llm_config: LLMConfig,
    ) -> MarkResponse:
        page = fetch_page_context(url)
        has_usable_context = len(page.extracted_text) >= 120
        system_prompt = build_page_system_prompt(
            page_title=page.title,
            page_url=page.url,
            user_hint=user_hint,
            has_usable_context=has_usable_context,
        )

        user_messages: list[dict[str, str]] = [primary_page_context_message(page)]
        merged_hint, llm_image_paths = self._prepare_image_context(user_hint, image_paths)
        if merged_hint:
            user_messages.append({"role": "user", "content": merged_hint})
        elif llm_image_paths:
            user_messages.append({"role": "user", "content": "Bookmark this page."})

        response_text = self._generate_note_json(
            llm_config=llm_config,
            system_prompt=system_prompt,
            user_messages=user_messages,
            image_paths=llm_image_paths,
            fallback_title=page.title,
        )
        parsed = parse_generated_note(response_text, fallback_title=page.title)

        body = parsed.body
        captured_at = datetime.now(timezone.utc)
        body = self._append_linq_assets(body, vault_root, image_paths, captured_at)

        write_result = write_note(
            WriteInput(
                title=parsed.title,
                body=body,
                source_url=page.url,
                references=[Reference(title=page.title, url=page.url)],
                created_at=captured_at,
                export_folder=vault_root,
                export_kind=ExportKind.MARK_PAGE,
            )
        )

        chunks_indexed = self._maybe_sync_index(request.sync_index, vault_root)
        return MarkResponse(
            title=write_result.title,
            file_path=str(write_result.file_path),
            mode="page",
            chunks_indexed=chunks_indexed,
        )

    def _capture_standalone(
        self,
        *,
        request: CaptureRequest,
        vault_root: Path,
        user_hint: str,
        image_paths: list[Path],
        llm_config: LLMConfig,
    ) -> MarkResponse:
        if not user_hint and not image_paths:
            raise ValueError("Provide text and/or at least one image to capture.")

        system_prompt = build_standalone_system_prompt(
            user_hint=user_hint,
            has_images=bool(image_paths),
        )
        merged_hint, llm_image_paths = self._prepare_image_context(user_hint, image_paths)
        capture_text = merged_hint or "Save this image capture."
        fallback_title = user_hint[:60] if user_hint else "Mobile capture"
        response_text = self._generate_note_json(
            llm_config=llm_config,
            system_prompt=system_prompt,
            user_messages=[{"role": "user", "content": capture_text}],
            image_paths=llm_image_paths,
            fallback_title=fallback_title,
        )
        parsed = parse_generated_note(response_text, fallback_title=fallback_title)

        captured_at = datetime.now(timezone.utc)
        body = self._append_linq_assets(parsed.body, vault_root, image_paths, captured_at)
        write_result = write_note(
            WriteInput(
                title=parsed.title,
                body=body,
                source_url=None,
                references=[],
                created_at=captured_at,
                export_folder=vault_root,
                export_kind=ExportKind.MARK_STANDALONE,
            )
        )

        chunks_indexed = self._maybe_sync_index(request.sync_index, vault_root)
        return MarkResponse(
            title=write_result.title,
            file_path=str(write_result.file_path),
            mode="standalone",
            chunks_indexed=chunks_indexed,
        )

    def _maybe_sync_index(self, sync_index: bool, vault_root: Path) -> int | None:
        if not sync_index:
            return None
        result = self.search_service.sync_index(str(vault_root))
        return result.chunks_indexed

    def _prepare_image_context(
        self,
        user_hint: str,
        image_paths: list[Path],
    ) -> tuple[str, list[Path]]:
        merged_hint, llm_paths = prepare_image_context(
            user_hint,
            image_paths,
            ocr_enabled=settings.ocr_enabled,
            automatically_detect_language=settings.ocr_auto_detect_language,
        )
        if settings.mark_embed_images and image_paths:
            return merged_hint, []
        return merged_hint, llm_paths

    def _append_linq_assets(
        self,
        body: str,
        vault_root: Path,
        image_paths: list[Path],
        captured_at: datetime,
    ) -> str:
        if not settings.mark_embed_images or not image_paths:
            return body
        return append_linq_asset_images(
            body,
            vault_root=vault_root,
            image_paths=image_paths,
            captured_at=captured_at,
        )

    def _generate_note_json(
        self,
        *,
        llm_config: LLMConfig,
        system_prompt: str,
        user_messages: list[dict[str, str]],
        image_paths: list[Path],
        fallback_title: str,
    ) -> str:
        response_text = chat_text(
            llm_config,
            system_prompt,
            user_messages,
            image_paths=image_paths,
            num_predict=settings.mark_llm_num_predict,
        )
        try:
            parse_generated_note(response_text, fallback_title=fallback_title)
            return response_text
        except MarkParseError:
            retry_messages = [
                *user_messages,
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": JSON_RETRY_USER_MESSAGE},
            ]
            retry_text = chat_text(
                llm_config,
                system_prompt,
                retry_messages,
                image_paths=image_paths,
                num_predict=settings.mark_llm_num_predict,
            )
            parse_generated_note(retry_text, fallback_title=fallback_title)
            return retry_text


__all__ = ["MarkService", "MarkParseError"]
