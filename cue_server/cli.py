from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import uvicorn

from cue.config import settings
from cue_mark.models import CaptureRequest
from cue_mark.service import MarkService
from cue_mark.telegram.handler import TelegramUpdateHandler
from cue_mark.telegram.poller import run_poller
from cue_mark.telegram.store import TelegramEventStore
from cue_search.models import LLMConfig, SearchRequest
from cue_search.search_service import SearchService
from cue_server.logging_config import uvicorn_log_config

logger = logging.getLogger(__name__)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Cue agentic backend")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Start the unified HTTP server")

    mark_parser = subparsers.add_parser("mark", help="Mark capture commands")
    mark_subparsers = mark_parser.add_subparsers(dest="mark_command")

    capture_parser = mark_subparsers.add_parser("capture", help="Capture a bookmark locally")
    capture_parser.add_argument("--text", default="", help="User hint or note text")
    capture_parser.add_argument("--url", action="append", default=[], dest="urls")
    capture_parser.add_argument("--image", action="append", default=[], dest="images")
    capture_parser.add_argument("--no-sync-index", action="store_true")

    telegram_parser = subparsers.add_parser("telegram", help="Telegram bot utilities")
    telegram_subparsers = telegram_parser.add_subparsers(dest="telegram_command")
    telegram_subparsers.add_parser("poll", help="Run Telegram long-polling worker")
    simulate_parser = telegram_subparsers.add_parser(
        "simulate",
        help="Process a saved Telegram Update JSON locally",
    )
    simulate_parser.add_argument("payload_file")
    jobs_parser = telegram_subparsers.add_parser("jobs", help="Show job status for an update")
    jobs_parser.add_argument("update_id")

    ocr_parser = subparsers.add_parser("ocr", help="Extract text from an image with Apple Vision")
    ocr_parser.add_argument("image_path")
    ocr_parser.add_argument(
        "--auto-detect-language",
        action="store_true",
        help="Enable Vision language auto-detection (default: English only)",
    )

    index_parser = subparsers.add_parser("index", help="Rebuild the note index")
    index_parser.add_argument("corpus_root")

    query_parser = subparsers.add_parser("query", help="Run a local search query")
    query_parser.add_argument("corpus_root")
    query_parser.add_argument("query")
    query_parser.add_argument("--model", default="gemma4:e4b-mlx")
    query_parser.add_argument("--base-url", default="http://localhost:11434")

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run(
            "cue_server.main:app",
            host=settings.host,
            port=settings.port,
            reload=False,
            log_config=uvicorn_log_config(),
        )
        return

    if args.command == "mark" and args.mark_command == "capture":
        service = MarkService()
        response = service.capture(
            CaptureRequest(
                text=args.text,
                urls=args.urls,
                image_paths=args.images,
                sync_index=not args.no_sync_index,
            )
        )
        print(json.dumps(response.model_dump(), indent=2))
        return

    if args.command == "telegram" and args.telegram_command == "poll":
        logging.basicConfig(level=logging.INFO)
        run_poller()
        return

    if args.command == "telegram" and args.telegram_command == "simulate":
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        handler = TelegramUpdateHandler()
        status, inbound = handler.accept_update(payload)
        print(json.dumps(status, indent=2))
        if inbound is not None:
            handler.process_inbound(inbound)
        return

    if args.command == "telegram" and args.telegram_command == "jobs":
        store = TelegramEventStore(settings.telegram_jobs_db_file)
        row = store.get(args.update_id)
        if row is None:
            raise SystemExit(f"Unknown Telegram update: {args.update_id}")
        print(json.dumps(row, indent=2))
        return

    if args.command == "ocr":
        from cue.ocr.formatting import attachment_section
        from cue.ocr.service import extract_text_blocks_from_paths, vision_ocr_available

        if not vision_ocr_available():
            raise SystemExit("Apple Vision OCR is only available on macOS with PyObjC installed.")

        blocks = extract_text_blocks_from_paths(
            [Path(args.image_path)],
            automatically_detect_language=args.auto_detect_language,
        )
        print(attachment_section(1, blocks))
        return

    search_service = SearchService()

    if args.command == "index":
        result = search_service.rebuild_index(args.corpus_root)
        print(json.dumps(result.__dict__, indent=2))
        return

    if args.command == "query":
        response = search_service.search(
            SearchRequest(
                query=args.query,
                corpus_root=args.corpus_root,
                llm=LLMConfig(
                    provider="ollama",
                    base_url=args.base_url,
                    model=args.model,
                ),
            )
        )
        print(response.model_dump_json(indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    cli()
