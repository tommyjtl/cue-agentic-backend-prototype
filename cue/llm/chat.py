from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from cue_search.llm.ollama import OllamaChatClient
from cue_search.llm.openai import OpenAIChatClient
from cue_search.models import LLMConfig


def chat_text(
    config: LLMConfig,
    system_prompt: str,
    messages: list[dict[str, Any]],
    *,
    image_paths: list[Path] | None = None,
) -> str:
    payload_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    payload_messages.extend(messages)

    if image_paths and config.provider == "ollama":
        payload_messages = _attach_ollama_images(payload_messages, image_paths)

    if config.provider == "openai":
        client = OpenAIChatClient(config)
    else:
        client = OllamaChatClient(config)

    response = client.chat(payload_messages)
    content = (response.get("content") or "").strip()
    if not content:
        raise RuntimeError("LLM returned an empty response.")
    return content


def _attach_ollama_images(
    messages: list[dict[str, Any]],
    image_paths: list[Path],
) -> list[dict[str, Any]]:
    encoded = []
    for path in image_paths:
        encoded.append(base64.b64encode(path.read_bytes()).decode("ascii"))

    if not encoded:
        return messages

    updated = list(messages)
    for index in range(len(updated) - 1, -1, -1):
        if updated[index].get("role") == "user":
            message = dict(updated[index])
            message["images"] = encoded
            updated[index] = message
            return updated

    updated.append({"role": "user", "content": "See attached image(s).", "images": encoded})
    return updated
