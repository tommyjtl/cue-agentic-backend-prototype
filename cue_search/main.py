from __future__ import annotations

import argparse
import json

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cue_search.config import settings
from cue_search.models import HealthResponse, IndexResponse, LLMConfig, SearchRequest, SearchResponse
from cue_search.search_service import SearchService

app = FastAPI(title="cue-search", version="0.1.0")
service = SearchService()


class IndexRequest(BaseModel):
    corpus_root: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    payload = service.health()
    return HealthResponse(status=str(payload["status"]), chunk_count=int(payload["chunk_count"]))


@app.post("/v1/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    try:
        return service.search(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/index/rebuild", response_model=IndexResponse)
def rebuild_index(request: IndexRequest) -> IndexResponse:
    try:
        result = service.rebuild_index(request.corpus_root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IndexResponse(
        files_scanned=result.files_scanned,
        chunks_indexed=result.chunks_indexed,
        corpus_root=result.corpus_root,
    )


@app.post("/v1/index/sync", response_model=IndexResponse)
def sync_index(request: IndexRequest) -> IndexResponse:
    try:
        result = service.sync_index(request.corpus_root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IndexResponse(
        files_scanned=result.files_scanned,
        chunks_indexed=result.chunks_indexed,
        corpus_root=result.corpus_root,
    )


def cli() -> None:
    parser = argparse.ArgumentParser(description="cue-search sidecar")
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
        uvicorn.run("cue_search.main:app", host=settings.host, port=settings.port, reload=False)
        return

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
