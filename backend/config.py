"""Centralized Configuration for MCP Enterprise Data Analyst.

Reads configuration from environment variables and .env file.
Enforces security: never hardcode credentials or keys.
"""

from typing import Any, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Settings (Groq only, using openai/gpt-oss-120b)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TEMPERATURE: float = 0.0

    # MySQL Settings
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "enterprise_analytics"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_POOL_SIZE: int = 5

    # ChromaDB Settings
    CHROMA_HOST: Optional[str] = None
    CHROMA_PORT: Optional[int] = None
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "enterprise_policies"

    @field_validator("CHROMA_PORT", mode="before")
    @classmethod
    def parse_optional_int(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        return int(v)

    @field_validator("CHROMA_HOST", mode="before")
    @classmethod
    def parse_optional_str(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return str(v)

    # Hybrid RAG & Reranker Settings
    SEMANTIC_WEIGHT: float = 0.6
    KEYWORD_WEIGHT: float = 0.4
    TOP_K: int = 5
    RERANKER_ENABLED: bool = True

    # Guardrails & Safety Parameters
    MAX_ROWS: int = 1000
    QUERY_TIMEOUT: int = 10
    MAX_INPUT_LENGTH: int = 2000
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
