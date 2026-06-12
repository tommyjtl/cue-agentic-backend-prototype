from __future__ import annotations

import argparse
import json

import uvicorn

from cue.config import settings
from cue_search.models import LLMConfig, SearchRequest
from cue_search.search_service import SearchService
from cue_server.logging_config import uvicorn_log_config


def cli() -> None:
    parser = argparse.ArgumentParser(description="cue-search sidecar (legacy entrypoint)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Start the HTTP server")

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

    service = SearchService()

    if args.command == "index":
        result = service.rebuild_index(args.corpus_root)
        print(json.dumps(result.__dict__, indent=2))
        return

    if args.command == "query":
        response = service.search(
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
