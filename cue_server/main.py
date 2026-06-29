from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cue.config import settings
from cue_mark.models import CaptureRequest, MarkResponse
from cue_mark.parser import MarkParseError
from cue_mark.service import MarkService
from cue_search.models import HealthResponse, IndexResponse, SearchRequest, SearchResponse
from cue_search.search_service import SearchService
from cue_server.security import PublicRouteGuardMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="cue-backend", version="0.3.0")
app.add_middleware(PublicRouteGuardMiddleware)
search_service = SearchService()
mark_service = MarkService(search_service)


class IndexRequest(BaseModel):
    corpus_root: str


class BackendHealthResponse(BaseModel):
    status: str
    chunk_count: int
    mark_vault_configured: bool
    telegram_configured: bool


@app.get("/health", response_model=BackendHealthResponse)
def health() -> BackendHealthResponse:
    payload = search_service.health()
    return BackendHealthResponse(
        status=str(payload["status"]),
        chunk_count=int(payload["chunk_count"]),
        mark_vault_configured=bool(settings.mark_vault_root.strip()),
        telegram_configured=settings.telegram_configured,
    )


@app.post("/v1/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    try:
        return search_service.search(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/index/rebuild", response_model=IndexResponse)
def rebuild_index(request: IndexRequest) -> IndexResponse:
    try:
        result = search_service.rebuild_index(request.corpus_root)
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
        result = search_service.sync_index(request.corpus_root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IndexResponse(
        files_scanned=result.files_scanned,
        chunks_indexed=result.chunks_indexed,
        corpus_root=result.corpus_root,
    )


@app.post("/v1/mark/capture", response_model=MarkResponse)
def mark_capture(request: CaptureRequest) -> MarkResponse:
    try:
        return mark_service.capture(request)
    except MarkParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Backward-compatible alias for older health clients.
@app.get("/health/search", response_model=HealthResponse, include_in_schema=False)
def search_health() -> HealthResponse:
    payload = search_service.health()
    return HealthResponse(status=str(payload["status"]), chunk_count=int(payload["chunk_count"]))
