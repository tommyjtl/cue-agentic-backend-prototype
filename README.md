# Cue agentic backend

Python backend for Cue **mark capture** and **`/search`**: indexes bookmark markdown in LanceDB, runs agentic RAG for search, and captures new bookmarks from CLI (Linq webhook coming next).

macOS Cue app is unchanged — it keeps using `/v1/search` on localhost.

## Setup

```bash
cd ~/Documents/Projects/cue-agentic-backend-prototype
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires **Ollama** running locally with:

- Embedding model (default: `snowflake-arctic-embed2:latest`)
- Chat model for search (default: `gemma4:e4b-mlx`)
- Chat/vision model for mark (default: `gemma4:e4b-mlx`)

## Config

Create `.env` or export:

```bash
export CUE_MARK_VAULT_ROOT="$HOME/Documents/Obsidian/Tommy's Life/Tommy/bookmarks"
export CUE_MARK_LLM_PROVIDER=ollama
export CUE_MARK_LLM_BASE_URL=http://localhost:11434
export CUE_MARK_LLM_MODEL=gemma4:e4b-mlx
```

Search settings still use `CUE_SEARCH_*` (see below).

## Run the unified server

```bash
cue serve
# legacy alias still works:
cue-search serve
```

Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Combined health + mark vault status |
| `POST` | `/v1/search` | Agentic search over bookmarks |
| `POST` | `/v1/index/rebuild` | Rebuild LanceDB index |
| `POST` | `/v1/index/sync` | Sync index after new notes |
| `POST` | `/v1/mark/capture` | Capture a bookmark |

## Mark capture (CLI)

```bash
cue mark capture \
  --text "MLX agent orchestration patterns" \
  --url "https://example.com/post"
```

With image (Apple Vision OCR by default on macOS):

```bash
cue mark capture --text "Save this screenshot" --image ~/Desktop/shot.png
cue ocr ~/Desktop/shot.png
cue ocr ~/Desktop/shot.png --auto-detect-language
```

HTTP:

```bash
curl -s http://127.0.0.1:8765/v1/mark/capture \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "MLX agents",
    "urls": ["https://example.com/post"]
  }' | python3 -m json.tool
```

Each successful capture writes `{vault}/{yyyy-MM-dd}/{title}.md` and syncs the search index when `sync_index` is true (default).

## Search (unchanged)

```bash
export CORPUS="$HOME/Documents/Obsidian/Tommy's Life/Tommy/bookmarks"

cue index "$CORPUS"
cue query "$CORPUS" "what did I save about MLX agents?"
```

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

## Environment variables

| Variable | Default |
|----------|---------|
| `CUE_HOST` / `CUE_SEARCH_HOST` | `127.0.0.1` |
| `CUE_PORT` / `CUE_SEARCH_PORT` | `8765` |
| `CUE_MARK_VAULT_ROOT` | _(required for mark)_ |
| `CUE_MARK_LLM_PROVIDER` | `ollama` |
| `CUE_MARK_LLM_BASE_URL` | `http://localhost:11434` |
| `CUE_MARK_LLM_MODEL` | `gemma4:e4b-mlx` |
| `CUE_OCR_ENABLED` | `true` (macOS Apple Vision) |
| `CUE_OCR_AUTO_DETECT_LANGUAGE` | `false` (off = English only) |
| `CUE_SEARCH_LANCEDB_PATH` | `~/Library/Application Support/Cue/search/lancedb` |
| `CUE_SEARCH_EMBEDDINGS_MODEL` | `snowflake-arctic-embed2:latest` |

## Tests

```bash
pytest
```

Integration tests that call Ollama or fetch URLs are manual via `cue mark capture` and `cue query`.

## Next: Linq + FRP

Phase 2 adds iMessage capture via Linq. Configure:

```bash
export CUE_LINQ_API_KEY="..."
export CUE_LINQ_WEBHOOK_SECRET="whsec_..."   # from webhook subscription create response
export CUE_LINQ_ALLOWED_SENDERS="+1xxxxxxxxxx"  # your phone number (comma-separated)
```

Create a Linq webhook subscription pointing at your public FRP URL:

```bash
curl -X POST https://api.linqapp.com/api/partner/v3/webhook-subscriptions \
  -H "Authorization: Bearer $CUE_LINQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://cue.example.com/v1/linq/webhook",
    "subscribed_events": ["message.received"]
  }'
```

Store the returned `signing_secret` as `CUE_LINQ_WEBHOOK_SECRET`.

Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/linq/webhook` | Linq inbound (verify signature, enqueue mark job) |
| `GET` | `/v1/linq/jobs/{event_id}` | Job status for debugging |

Local webhook simulation without Linq:

```bash
cue linq simulate ./sample-message-received.json
```

Flow: iMessage → Linq → FRP → `cue serve` → mark pipeline → Obsidian note → iMessage reply `Saved: {title}`.

### iMessage commands

Text messages can start with these commands (case-insensitive, prefix only):

| Message | Action | Reply |
|---------|--------|-------|
| `search your question` | Search bookmarks (summary only) | Answer text |
| `search` | — | Usage hint |
| `reindex` | Sync LanceDB index | `Indexed N chunks from M files.` |
| anything else | Mark capture | `Saved: {title}` |

Examples:

```
search what did I save about frp?
reindex
```
