from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def expand_user_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("CUE_HOST", "CUE_SEARCH_HOST"),
    )
    port: int = Field(
        default=8765, validation_alias=AliasChoices("CUE_PORT", "CUE_SEARCH_PORT")
    )

    mark_vault_root: str = Field(default="", validation_alias="CUE_MARK_VAULT_ROOT")
    mark_llm_provider: Literal["ollama", "openai"] = Field(
        default="ollama", validation_alias="CUE_MARK_LLM_PROVIDER"
    )
    mark_llm_base_url: str = Field(
        default="http://localhost:11434", validation_alias="CUE_MARK_LLM_BASE_URL"
    )
    mark_llm_model: str = Field(
        default="gemma4:e4b-mlx", validation_alias="CUE_MARK_LLM_MODEL"
    )
    mark_llm_api_key: str = Field(default="", validation_alias="CUE_MARK_LLM_API_KEY")

    search_llm_model: str = Field(default="", validation_alias="CUE_SEARCH_LLM_MODEL")

    lancedb_path: str = Field(
        default="~/Library/Application Support/Cue/search/lancedb",
        validation_alias="CUE_SEARCH_LANCEDB_PATH",
    )
    indexer_state_path: str = Field(
        default="~/Library/Application Support/Cue/search/indexer-state.json",
        validation_alias="CUE_SEARCH_INDEXER_STATE_PATH",
    )

    embeddings_provider: str = Field(
        default="ollama", validation_alias="CUE_SEARCH_EMBEDDINGS_PROVIDER"
    )
    embeddings_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias="CUE_SEARCH_EMBEDDINGS_BASE_URL",
    )
    embeddings_model: str = Field(
        default="snowflake-arctic-embed2:latest",
        validation_alias="CUE_SEARCH_EMBEDDINGS_MODEL",
    )

    agent_max_turns: int = Field(
        default=4, validation_alias="CUE_SEARCH_AGENT_MAX_TURNS"
    )
    default_max_sources: int = Field(
        default=5, validation_alias="CUE_SEARCH_DEFAULT_MAX_SOURCES"
    )
    retrieval_top_k: int = Field(
        default=8, validation_alias="CUE_SEARCH_RETRIEVAL_TOP_K"
    )

    linq_api_base_url: str = Field(
        default="https://api.linqapp.com/api/partner/v3",
        validation_alias="CUE_LINQ_API_BASE_URL",
    )
    linq_api_key: str = Field(default="", validation_alias="CUE_LINQ_API_KEY")
    linq_webhook_secret: str = Field(
        default="", validation_alias="CUE_LINQ_WEBHOOK_SECRET"
    )
    linq_allowed_senders: str = Field(
        default="", validation_alias="CUE_LINQ_ALLOWED_SENDERS"
    )
    linq_jobs_db_path: str = Field(
        default="~/Library/Application Support/Cue/linq-jobs.sqlite3",
        validation_alias="CUE_LINQ_JOBS_DB_PATH",
    )
    linq_webhook_max_age_seconds: int = Field(
        default=300,
        validation_alias="CUE_LINQ_WEBHOOK_MAX_AGE_SECONDS",
    )

    ocr_enabled: bool = Field(default=True, validation_alias="CUE_OCR_ENABLED")
    ocr_auto_detect_language: bool = Field(
        default=False,
        validation_alias="CUE_OCR_AUTO_DETECT_LANGUAGE",
    )

    public_strict_routes: bool = Field(
        default=True,
        validation_alias="CUE_PUBLIC_STRICT_ROUTES",
    )
    public_expose_health: bool = Field(
        default=False,
        validation_alias="CUE_PUBLIC_EXPOSE_HEALTH",
    )
    webhook_rate_limit_per_minute: int = Field(
        default=60,
        validation_alias="CUE_WEBHOOK_RATE_LIMIT_PER_MINUTE",
    )

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

    @property
    def mark_vault_dir(self) -> Path:
        if not self.mark_vault_root.strip():
            raise ValueError("CUE_MARK_VAULT_ROOT is not configured.")
        return expand_user_path(self.mark_vault_root)

    @property
    def linq_jobs_db_file(self) -> Path:
        path = expand_user_path(self.linq_jobs_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def linq_allowed_sender_set(self) -> set[str]:
        values = [item.strip() for item in self.linq_allowed_senders.split(",")]
        return {item for item in values if item}

    @property
    def linq_configured(self) -> bool:
        return bool(self.linq_api_key.strip() and self.linq_webhook_secret.strip())

    @property
    def search_corpus_root(self) -> str:
        return self.mark_vault_root

    def search_llm_config(self):
        from cue_search.models import LLMConfig

        return LLMConfig(
            provider=self.mark_llm_provider,
            base_url=self.mark_llm_base_url,
            model=self.search_llm_model or self.mark_llm_model,
            api_key=self.mark_llm_api_key,
        )


settings = Settings()
