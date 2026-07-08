from functools import lru_cache
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore")

    app_name: str = "Property Rental Management System"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/rental_ai"
    debug: bool = False
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "GROK_API_KEY"),
    )
    groq_model: str = "openai/gpt-oss-120b"
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()