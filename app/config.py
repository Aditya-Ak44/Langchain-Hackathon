"""Application configuration management."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = Field(default="Content Aggregator API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    queue_workers: int = Field(default=2, alias="QUEUE_WORKERS")
    max_article_chars: int = Field(default=4000, alias="MAX_ARTICLE_CHARS")
    chunk_size_chars: int = Field(default=1200, alias="CHUNK_SIZE_CHARS")
    chunk_overlap_chars: int = Field(default=200, alias="CHUNK_OVERLAP_CHARS")
    max_chunks_per_item: int = Field(default=16, alias="MAX_CHUNKS_PER_ITEM")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2:3b", alias="OLLAMA_MODEL")
    ollama_generate_path: str = Field(default="/api/generate", alias="OLLAMA_GENERATE_PATH")
    langsmith_project_id: str = Field(
        default="3b885a48-08ec-4ec4-97f0-9532cee105b4",
        alias="LANGSMITH_PROJECT_ID",
    )
    langsmith_project: str = Field(default="Content Aggregation", alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )
    langsmith_tracing: bool = Field(default=True, alias="LANGSMITH_TRACING")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    tavily_base_url: str = Field(default="https://api.tavily.com", alias="TAVILY_BASE_URL")

    surrealdb_url: str = Field(default="ws://localhost:8000", alias="SURREALDB_URL")
    surrealdb_namespace: str = Field(default="content", alias="SURREALDB_NAMESPACE")
    surrealdb_database: str = Field(default="aggregator", alias="SURREALDB_DATABASE")
    surrealdb_username: str = Field(default="root", alias="SURREALDB_USERNAME")
    surrealdb_password: str = Field(default="root", alias="SURREALDB_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
