# Cue agentic backend

Python backend for Cue **mark capture** and **`/search`**: indexes bookmark markdown in LanceDB, runs agentic RAG for search, and captures new bookmarks from CLI or Telegram.

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

For gated pages (WeChat articles, JS-heavy sites), install the browser fetch extra:

```bash
pip install -e ".[dev,browser]"
playwright install chromium
```

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
| `CUE_MARK_LLM_NUM_PREDICT` | `4096` (Ollama max output tokens for mark notes) |
| `CUE_MARK_EMBED_IMAGES` | `true` (save Telegram/CLI images under `telegram-assets/`; OCR text only goes to LLM) |
| `CUE_OCR_ENABLED` | `true` (macOS Apple Vision) |
| `CUE_OCR_AUTO_DETECT_LANGUAGE` | `false` (off = English only) |
| `CUE_MARK_FETCH_MODE` | `auto` (`auto`, `http`, `browser`) |
| `CUE_MARK_BROWSER_FETCH_ENABLED` | `true` |
| `CUE_MARK_BROWSER_FETCH_HOSTS` | `mp.weixin.qq.com` |
| `CUE_MARK_BROWSER_FETCH_TIMEOUT_MS` | `30000` |
| `CUE_SEARCH_LANCEDB_PATH` | `~/Library/Application Support/Cue/search/lancedb` |
| `CUE_SEARCH_EMBEDDINGS_MODEL` | `snowflake-arctic-embed2:latest` |

## Tests

```bash
pytest
```

Integration tests that call Ollama or fetch URLs are manual via `cue mark capture` and `cue query`.

## Telegram capture

Capture bookmarks by DMing your bot in Telegram. Uses long polling — no public URL or tunnel required.

### 1. Create a bot

1. Open **@BotFather** in Telegram
2. Send `/newbot` and follow the prompts
3. Save the API token

Optional in BotFather:

- `/setdescription` — describe what the bot does
- `/setcommands` — e.g. `search`, `reindex`

### 2. Configure

Add to `.env`:

```bash
CUE_TELEGRAM_BOT_TOKEN="123456789:AAH..."
CUE_TELEGRAM_ALLOWED_USERS="123456789"   # your Telegram user ID (comma-separated)
```

Find your user ID by messaging [@userinfobot](https://t.me/userinfobot), or send your bot a message and inspect `getUpdates` output.

### 3. Run the poller

```bash
cue telegram poll
```

Open your bot in Telegram, tap **Start**, then send messages:

| Message | Action | Reply |
|---------|--------|-------|
| `ping` | Check allowlist (works even if not allowed yet) | `pong — you're allowed...` or your user id |
| `search your question` | Search bookmarks (summary only) | Answer text |
| `search` | — | Usage hint |
| `reindex` | Sync LanceDB index | `Indexed N chunks from M files.` |
| text, URL, or photo | Mark capture | `Saved: {title}` |

Examples:

```
https://example.com/post
search what did I save about frp?
reindex
```

Local simulation without Telegram:

```bash
cue telegram simulate ./sample-update.json
cue telegram jobs 10001
```

Flow: Telegram → `cue telegram poll` → mark pipeline → Obsidian note → Telegram reply `Saved: {title}`.

The HTTP server (`cue serve`) is optional for Telegram capture; keep it running if the macOS Cue app uses `/v1/search`.
