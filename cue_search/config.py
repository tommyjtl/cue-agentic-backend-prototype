from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def expand_user_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CUE_SEARCH_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8765

    lancedb_path: str = "~/Library/Application Support/Cue/search/lancedb"
    indexer_state_path: str = "~/Library/Application Support/Cue/search/indexer-state.json"

    embeddings_provider: str = "ollama"
    embeddings_base_url: str = "http://localhost:11434"
    embeddings_model: str = "snowflake-arctic-embed2:latest"

    agent_max_turns: int = 4
    default_max_sources: int = 5
    retrieval_top_k: int = 8

    @property
    def lancedb_dir(self) -> Path:
        path = expand_user_path(self.lancedb_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def indexer_state_file(self) -> Path:
        path = expand_user_path(self.indexer_state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
