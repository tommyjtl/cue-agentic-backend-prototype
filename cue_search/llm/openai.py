from __future__ import annotations

import json
from typing import Any

import httpx

from cue_search.models import LLMConfig


class OpenAIChatClient:
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
            "messages": messages,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": tool["function"],
                }
                for tool in tools
            ]

        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI chat/completions returned no choices.")

        message = choices[0].get("message") or {}
        normalized = {
            "role": message.get("role", "assistant"),
            "content": message.get("content"),
            "tool_calls": [],
        }

        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            normalized["tool_calls"].append(
                {
                    "function": {
                        "name": function.get("name"),
                        "arguments": function.get("arguments", "{}"),
                    }
                }
            )
        return normalized


def tool_messages_from_openai(message: dict[str, Any]) -> list[dict[str, Any]]:
    from cue_search.llm.ollama import parse_tool_calls

    calls = parse_tool_calls(message)
    return calls
