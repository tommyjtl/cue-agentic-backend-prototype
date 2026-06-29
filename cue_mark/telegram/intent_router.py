from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cue.config import settings
from cue.llm.chat import chat_text
from cue_mark.parser import _extract_json_payload, _strip_markdown_fences
from cue_search.models import LLMConfig

IntentKind = Literal["search", "reindex", "unknown"]
Confidence = Literal["high", "medium", "low"]

INTENT_SYSTEM_PROMPT = """You classify Telegram messages for a bookmark bot.

Pick exactly one intent:
- search — user asks about saved bookmarks or notes (questions, lookups, recall)
- reindex — user wants to rebuild or refresh the search index
- unknown — anything else (greetings, notes to save, unrelated chat, ambiguous messages)

The bot does NOT classify save/mark actions. Saving happens via URLs or when no search/reindex intent matches.

Examples:
- "Did I bookmark anything about AI agents?" -> search
- "What do I have on MLX?" -> search
- "Is there anything I saved about learning with AI?" -> search
- "Could you check if I saved any notes about AI?" -> search
- "Could you let me check if there is any note relevant to learning with AI?" -> search
- "Have I saved anything about this company? https://www.turing.com/" -> search
- "Refresh my search index" -> reindex
- "Sync the index" -> reindex
- "Remember that Embark uses dynamic documents" -> unknown
- "Hello" -> unknown

Respond with ONLY one JSON object:
{"intent":"search","confidence":"high","reason":"One short sentence.","search_query":"topic only"}

Rules:
- confidence must be high, medium, or low
- reason is one short sentence explaining your choice (shown to the user)
- search_query is required when intent is search; extract the topic, drop filler like "did I bookmark"
- questions about existing saved notes are always search, never unknown
- URLs in a question are context about what to search for, not a bookmark to save
- prefer unknown with low confidence over guessing search or reindex
"""

JSON_RETRY_USER_MESSAGE = (
    "Your previous reply was not valid JSON. Respond with ONLY one JSON object:\n"
    '{"intent":"search","confidence":"high","reason":"One short sentence.",'
    '"search_query":"topic"}\n'
    "Use intent search, reindex, or unknown. Use confidence high, medium, or low."
)

CLASSIFY_NUM_PREDICT = 256


class IntentParseError(ValueError):
    pass


@dataclass(frozen=True)
class IntentClassification:
    intent: IntentKind
    confidence: Confidence
    reason: str
    search_query: str = ""


def classify_intent(text: str, llm_config: LLMConfig | None = None) -> IntentClassification:
    config = llm_config or settings.search_llm_config()
    user_text = text.strip()
    if not user_text:
        return IntentClassification(
            intent="unknown",
            confidence="low",
            reason="The message was empty.",
        )

    response_text = chat_text(
        config,
        INTENT_SYSTEM_PROMPT,
        [{"role": "user", "content": user_text}],
        num_predict=CLASSIFY_NUM_PREDICT,
    )
    try:
        return parse_intent_response(response_text)
    except IntentParseError:
        retry_text = chat_text(
            config,
            INTENT_SYSTEM_PROMPT,
            [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": JSON_RETRY_USER_MESSAGE},
            ],
            num_predict=CLASSIFY_NUM_PREDICT,
        )
        return parse_intent_response(retry_text)


def parse_intent_response(response_text: str) -> IntentClassification:
    normalized = _strip_markdown_fences(response_text.strip())
    if not normalized:
        raise IntentParseError("Model returned an empty response.")

    payload = _extract_json_payload(normalized)
    if payload is None:
        raise IntentParseError("Model response did not contain valid JSON.")

    intent = str(payload.get("intent", "")).strip().lower()
    confidence = str(payload.get("confidence", "")).strip().lower()
    reason = str(payload.get("reason", "")).strip()
    search_query = str(payload.get("search_query", "")).strip()

    if intent not in {"search", "reindex", "unknown"}:
        raise IntentParseError(f"Unsupported intent: {intent!r}")
    if confidence not in {"high", "medium", "low"}:
        raise IntentParseError(f"Unsupported confidence: {confidence!r}")
    if not reason:
        raise IntentParseError("Model response did not include a reason.")
    if intent == "search" and not search_query:
        raise IntentParseError("Search intent requires search_query.")

    return IntentClassification(
        intent=intent,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        reason=reason,
        search_query=search_query,
    )


__all__ = [
    "CLASSIFY_NUM_PREDICT",
    "Confidence",
    "IntentClassification",
    "IntentKind",
    "IntentParseError",
    "classify_intent",
    "parse_intent_response",
]
