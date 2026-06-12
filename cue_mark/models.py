from typing import Literal

from pydantic import BaseModel, Field


class CaptureRequest(BaseModel):
    text: str = ""
    urls: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    sync_index: bool = True


class MarkResponse(BaseModel):
    title: str
    file_path: str
    mode: Literal["page", "standalone"]
    chunks_indexed: int | None = None
