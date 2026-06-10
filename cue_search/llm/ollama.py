from __future__ import annotations

import json
from typing import Any

import httpx

from cue_search.models import LLMConfig


class OllamaChatClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "stream": False,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(timeout=180.0) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama /api/chat returned an unexpected payload.")
        return message


def parse_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls = message.get("tool_calls") or []
    parsed: list[dict[str, Any]] = []
    for call in tool_calls:
        function = call.get("function") or {}
        name = function.get("name")
        raw_args = function.get("arguments", {})
        if isinstance(raw_args, str):
            arguments = json.loads(raw_args) if raw_args else {}
        elif isinstance(raw_args, dict):
            arguments = raw_args
        else:
            arguments = {}
        if name:
            parsed.append({"name": name, "arguments": arguments})
    return parsed
