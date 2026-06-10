SYSTEM_PROMPT = """You search the user's saved bookmark notes and answer their question.

Rules:
- Use the search_notes and read_note tools to find relevant material before answering.
- Answer only from note content returned by tools or the initial retrieval context.
- If nothing relevant exists, say so clearly.
- Write a concise excerpt-style answer (a short paragraph or a few bullets).
- At the end of your final message, append a JSON block on its own lines:

```json
{"cited_paths": ["/absolute/path/to/note.md"]}
```

Include only note file paths you actually used. Do not invent paths."""


def format_retrieval_context(chunks: list[dict]) -> str:
    if not chunks:
        return "Initial retrieval found no chunks."

    lines = ["Initial retrieval hits:"]
    for index, chunk in enumerate(chunks, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. {chunk.get('title', 'Untitled')} — {chunk.get('section', 'Body')}",
                    f"   path: {chunk.get('file_path', '')}",
                    f"   snippet: {str(chunk.get('text', ''))[:400]}",
                ]
            )
        )
    return "\n".join(lines)
