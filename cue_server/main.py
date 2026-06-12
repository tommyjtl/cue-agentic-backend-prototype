from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

from cue.config import settings
from cue_mark.linq.handler import LinqWebhookHandler, WebhookVerificationError, headers_from_request_headers
from cue_mark.linq.parser import LinqParseError
from cue_mark.linq.store import LinqEventStore
from cue_mark.models import CaptureRequest, MarkResponse
from cue_mark.parser import MarkParseError
from cue_mark.service import MarkService
from cue_search.models import HealthResponse, IndexResponse, SearchRequest, SearchResponse
from cue_search.search_service import SearchService
from cue_server.security import PublicRouteGuardMiddleware, WebhookRateLimitMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="cue-backend", version="0.3.0")
app.add_middleware(PublicRouteGuardMiddleware)
app.add_middleware(WebhookRateLimitMiddleware)
search_service = SearchService()
mark_service = MarkService(search_service)
linq_handler = LinqWebhookHandler(mark_service=mark_service, search_service=search_service)
linq_event_store = LinqEventStore(settings.linq_jobs_db_file)


class IndexRequest(BaseModel):
    corpus_root: str


class BackendHealthResponse(BaseModel):
    status: str
    chunk_count: int
    mark_vault_configured: bool
    linq_configured: bool


@app.get("/health", response_model=BackendHealthResponse)
def health() -> BackendHealthResponse:
    payload = search_service.health()
    return BackendHealthResponse(
        status=str(payload["status"]),
        chunk_count=int(payload["chunk_count"]),
        mark_vault_configured=bool(settings.mark_vault_root.strip()),
        linq_configured=settings.linq_configured,
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


class LinqJobResponse(BaseModel):
    event_id: str
    status: str
    chat_id: str | None = None
    sender_handle: str | None = None
    title: str | None = None
    file_path: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@app.post("/v1/linq/webhook")
async def linq_webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    if not settings.linq_configured:
        raise HTTPException(status_code=503, detail="Linq webhook is not configured.")

    body = await request.body()
    headers = headers_from_request_headers(dict(request.headers))

    try:
        result = linq_handler.accept_webhook(body=body, headers=headers)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LinqParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    inbound = result.pop("_inbound", None)
    if inbound is not None:
        background_tasks.add_task(linq_handler.process_inbound, inbound)

    return result


@app.get("/v1/linq/jobs/{event_id}", response_model=LinqJobResponse)
def linq_job_status(event_id: str) -> LinqJobResponse:
    row = linq_event_store.get(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown Linq event.")
    return LinqJobResponse(
        event_id=row["event_id"],
        status=row["status"],
        chat_id=row.get("chat_id"),
        sender_handle=row.get("sender_handle"),
        title=row.get("title"),
        file_path=row.get("file_path"),
        error=row.get("error"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# Backward-compatible alias for older health clients.
@app.get("/health/search", response_model=HealthResponse, include_in_schema=False)
def search_health() -> HealthResponse:
    payload = search_service.health()
    return HealthResponse(status=str(payload["status"]), chunk_count=int(payload["chunk_count"]))
