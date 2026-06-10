from typing import Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: Literal["ollama", "openai"]
    base_url: str
    model: str
    api_key: str = ""


class SearchRequest(BaseModel):
    query: str
    corpus_root: str
    llm: LLMConfig
    max_sources: int = Field(default=5, ge=1, le=10)


class SourceResult(BaseModel):
    file_path: str
    title: str
    excerpt: str
    section: str


class SearchDebug(BaseModel):
    tool_calls: int
    retrieval_chunks: int
    agent_turns: int


class SearchResponse(BaseModel):
    answer: str
    sources: list[SourceResult]
    debug: SearchDebug | None = None


class IndexResponse(BaseModel):
    files_scanned: int
    chunks_indexed: int
    corpus_root: str


class HealthResponse(BaseModel):
    status: str
    chunk_count: int
