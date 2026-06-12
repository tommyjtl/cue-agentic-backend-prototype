from __future__ import annotations

import json
import re
from pathlib import Path

from cue_search.agent.prompts import SYSTEM_PROMPT, format_retrieval_context
from cue_search.agent.tools import TOOL_DEFINITIONS, AgentTools
from cue_search.chunking import chunk_markdown_file, parse_frontmatter, infer_title
from cue_search.config import settings
from cue_search.indexer import NoteIndexer
from cue_search.llm.ollama import OllamaChatClient, parse_tool_calls
from cue_search.llm.openai import OpenAIChatClient
from cue_search.models import LLMConfig, SearchDebug, SearchRequest, SearchResponse, SourceResult
from cue_search.sandbox import validate_corpus_root
from cue_search.store import NoteStore

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class SearchService:
    def __init__(
        self,
        store: NoteStore | None = None,
        indexer: NoteIndexer | None = None,
    ) -> None:
        self.store = store or NoteStore()
        self.indexer = indexer or NoteIndexer(self.store)

    def health(self) -> dict[str, int | str]:
        stats = self.store.stats()
        return {"status": "ok", **stats}

    def rebuild_index(self, corpus_root: str):
        return self.indexer.rebuild(corpus_root)

    def sync_index(self, corpus_root: str):
        return self.indexer.sync(corpus_root)

    def search(self, request: SearchRequest) -> SearchResponse:
        validate_corpus_root(request.corpus_root)

        if self.store.stats()["chunk_count"] == 0:
            self.indexer.rebuild(request.corpus_root)

        retrieval_hits = self.store.search(
            request.query,
            limit=settings.retrieval_top_k,
        )
        tools = AgentTools(self.store, request.corpus_root)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": format_retrieval_context(retrieval_hits),
            },
            {"role": "user", "content": request.query},
        ]

        tool_call_count = 0
        agent_turns = 0
        final_content = ""

        for _ in range(settings.agent_max_turns):
            agent_turns += 1
            message = self._chat(request.llm, messages, TOOL_DEFINITIONS)
            tool_calls = parse_tool_calls(message)

            if tool_calls:
                messages.append(message)
                for call in tool_calls:
                    tool_call_count += 1
                    result = tools.execute(call["name"], call["arguments"])
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": call["name"],
                            "content": result,
                        }
                    )
                continue

            final_content = (message.get("content") or "").strip()
            break

        if not final_content:
            final_content = "I could not find an answer in your saved notes."

        cited_paths, cleaned_answer = self._extract_cited_paths(final_content)
        sources: list[SourceResult] = []
        if not request.summary_only:
            sources = self._build_sources(
                cited_paths=cited_paths,
                retrieval_hits=retrieval_hits,
                corpus_root=request.corpus_root,
                max_sources=request.max_sources,
            )

        debug = None if request.summary_only else SearchDebug(
            tool_calls=tool_call_count,
            retrieval_chunks=len(retrieval_hits),
            agent_turns=agent_turns,
        )

        return SearchResponse(
            answer=cleaned_answer,
            sources=sources,
            debug=debug,
        )

    def _chat(self, llm: LLMConfig, messages: list[dict], tools: list[dict]) -> dict:
        if llm.provider == "openai":
            client = OpenAIChatClient(llm)
        else:
            client = OllamaChatClient(llm)
        return client.chat(messages, tools=tools)

    def _extract_cited_paths(self, content: str) -> tuple[list[str], str]:
        match = JSON_BLOCK_RE.search(content)
        cited_paths: list[str] = []
        cleaned = content

        if match:
            try:
                payload = json.loads(match.group(1))
                raw_paths = payload.get("cited_paths") or []
                if isinstance(raw_paths, list):
                    cited_paths = [str(path) for path in raw_paths if path]
            except json.JSONDecodeError:
                pass
            cleaned = content[: match.start()].strip()

        return cited_paths, cleaned

    def _build_sources(
        self,
        cited_paths: list[str],
        retrieval_hits: list[dict],
        corpus_root: str,
        max_sources: int,
    ) -> list[SourceResult]:
        hit_by_path = {hit.get("file_path"): hit for hit in retrieval_hits}
        ordered_paths: list[str] = []

        for path in cited_paths:
            if path not in ordered_paths:
                ordered_paths.append(path)

        for hit in retrieval_hits:
            file_path = hit.get("file_path")
            if file_path and file_path not in ordered_paths:
                ordered_paths.append(file_path)

        sources: list[SourceResult] = []
        for file_path in ordered_paths[:max_sources]:
            hit = hit_by_path.get(file_path)
            path = Path(file_path)
            if hit:
                sources.append(
                    SourceResult(
                        file_path=file_path,
                        title=str(hit.get("title") or path.stem),
                        excerpt=str(hit.get("text", ""))[:400].strip(),
                        section=str(hit.get("section") or "Body"),
                    )
                )
                continue

            if not path.exists():
                continue

            raw = path.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(raw)
            title = infer_title(metadata, body)
            excerpt = body.strip()[:400]
            sources.append(
                SourceResult(
                    file_path=str(path.resolve()),
                    title=title,
                    excerpt=excerpt,
                    section="Body",
                )
            )

        return sources
