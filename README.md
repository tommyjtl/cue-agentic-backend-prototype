# cue-search (Cue agentic backend prototype)

Python sidecar for Cue `/search`: indexes mark-export markdown notes in LanceDB, runs a small agentic RAG loop, and returns `{ answer, sources[] }`.

## Setup

```bash
cd ~/Documents/Projects/cue-agentic-backend-prototype
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires **Ollama** running locally with:

- Embedding model (default: `snowflake-arctic-embed2:latest`)
- Chat model with tool support (default in CLI: `gemma4:e4b-mlx`)

## Quick test (CLI)

```bash
export CORPUS="$HOME/Documents/Obsidian/Tommy's Life/Tommy/bookmarks"

# 1. Build the index
cue-search index "$CORPUS"

# 2. Run a query
cue-search query "$CORPUS" "what did I save about MLX agents?"
```

## HTTP server

```bash
cue-search serve
```

Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Sidecar status + chunk count |
| `POST` | `/v1/index/rebuild` | `{ "corpus_root": "..." }` |
| `POST` | `/v1/index/sync` | incremental (same as rebuild in v0) |
| `POST` | `/v1/search` | search request with provider pass-through |

Example search request:

```bash
curl -s http://127.0.0.1:8765/v1/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "what did I save about MLX?",
    "corpus_root": "'"$CORPUS"'",
    "llm": {
      "provider": "ollama",
      "base_url": "http://localhost:11434",
      "model": "gemma4:e4b-mlx",
      "api_key": ""
    }
  }' | python3 -m json.tool
```

## Config

Environment variables (optional):

| Variable | Default |
|----------|---------|
| `CUE_SEARCH_HOST` | `127.0.0.1` |
| `CUE_SEARCH_PORT` | `8765` |
| `CUE_SEARCH_EMBEDDINGS_MODEL` | `snowflake-arctic-embed2:latest` |
| `CUE_SEARCH_EMBEDDINGS_BASE_URL` | `http://localhost:11434` |

## Tests

```bash
pytest
```

Integration tests that call Ollama are manual via `cue-search query` for now.
